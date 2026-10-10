import json
from datetime import datetime, timezone

from backend.code_fix_suggestions import LLMCodeFixSuggestionService
from backend.code_patch_execution import LLMCodePatchExecutionService
from backend.code_patch_planning import LLMCodePatchService
from backend.code_patch_regression import CRITICAL as REGRESSION_CRITICAL
from backend.code_patch_regression import LLMCodePatchRegressionService
from backend.code_patch_security_review import CRITICAL as SECURITY_CRITICAL
from backend.code_patch_security_review import DEPENDENCY as SECURITY_DEPENDENCY
from backend.code_patch_security_review import LLMCodePatchSecurityService
from backend.code_patch_verification import LLMCodePatchVerificationService
from backend.compilation_plan import ENDPOINT_METHODS
from backend.generated_code_review import LLMGeneratedCodeReviewService
from backend.llm.context import LLMContextItem
from backend.llm.routing import LLMRouteRequest

from .models import LLMCodePatchCompatibility

_LLM_CATEGORIES = frozenset({"GENERATED_STRUCTURE", "SCHEMA_INCOMPATIBILITY", "IMPORT_INCOMPATIBILITY"})

COMPATIBILITY_SYSTEM_PROMPT = (
    "You are a compiler compatibility reviewer performing a final check on "
    "an already-applied patch's current generated output, before it may be "
    "accepted. You are given that output verbatim. The existing compiler "
    "only supports a fixed set of route methods and generation "
    "conventions -- identify anything about this output the compiler's own "
    "generation approach could not actually handle. Respond with ONLY a "
    "single JSON object -- no prose, no markdown fencing -- of the form "
    "{\"findings\": [...], \"confidence\": 0.0}. 'findings' may be an "
    "empty list if nothing stands out. Each finding is an object with: "
    "'category' (one of GENERATED_STRUCTURE, SCHEMA_INCOMPATIBILITY, "
    "IMPORT_INCOMPATIBILITY), 'message' (why this is a problem), and "
    "'blocking' (true if the patch must not be accepted until fixed, "
    "false if advisory). 'confidence' is a number between 0.0 and 1.0 for "
    "the review as a whole. This is a read-only review -- never propose "
    "editing the generated output, the compiler, or anything upstream of "
    "it."
)


class MalformedCompatibilityResponseError(ValueError):
    """Raised when the LLM's compatibility response isn't well-formed."""


class UnverifiedPatchError(ValueError):
    """Raised when review() is called for an execution that hasn't passed Commit #6 syntax verification."""


class UnknownCompatibilityReviewError(KeyError):
    """Raised when findings()/compatible() is called before review() for an execution_id."""


def _finding(category: str, message: str, blocking: bool) -> dict:
    return {"category": category, "message": message, "blocking": blocking}


class LLMCodePatchCompatibilityService:
    """The final compiler-compatibility gate for one applied Commit #5 execution.

    Reuses Commit #7's LLMCodePatchRegressionService.regressions() for
    schema/structure incompatibilities and Commit #8's
    LLMCodePatchSecurityService.findings() for dependency/security
    incompatibilities -- this service never recomputes either, it only
    aggregates them. Its own deterministic check reuses
    backend.compilation_plan.ENDPOINT_METHODS, the same set of HTTP
    methods the existing compiler already supports, against any endpoints
    the current generated output describes. The LLM (same orchestration
    pipeline used throughout) is only asked about the existing compiler's
    own generation approach, and every finding it proposes must fall in a
    real category. review() never writes to the generated output, the
    execution, or anything upstream of it.
    """

    def __init__(
        self,
        verification_service: LLMCodePatchVerificationService,
        regression_service: LLMCodePatchRegressionService,
        security_service: LLMCodePatchSecurityService,
        execution_service: LLMCodePatchExecutionService,
        patch_service: LLMCodePatchService,
        fix_service: LLMCodeFixSuggestionService,
        review_service: LLMGeneratedCodeReviewService,
        orchestration_service,
        context_service,
        route_request: LLMRouteRequest = None,
    ):
        self._verification_service = verification_service
        self._regression_service = regression_service
        self._security_service = security_service
        self._execution_service = execution_service
        self._patch_service = patch_service
        self._fix_service = fix_service
        self._review_service = review_service
        self._orchestration_service = orchestration_service
        self._context_service = context_service
        self._route_request = route_request or LLMRouteRequest(
            task="code_patch_compatibility_review", required_capabilities=["chat"]
        )
        self._reviews = {}
        self._request_counter = 0
        self._review_counter = 0

    def _resolve_output(self, execution_id: str) -> dict:
        execution = self._execution_service.get(execution_id)
        plan = self._patch_service.get(execution.plan_id)
        suggestion = self._fix_service.get(plan.suggestion_id)
        review = self._review_service.get(suggestion.review_id)
        return self._review_service.get_generated_output(review.target).output

    @staticmethod
    def _route_findings(output: dict) -> list:
        endpoints = output.get("endpoints")
        if not isinstance(endpoints, list):
            return []

        findings = []
        for endpoint in endpoints:
            if not isinstance(endpoint, dict):
                continue
            method = endpoint.get("method")
            path = endpoint.get("path")
            if method not in ENDPOINT_METHODS:
                findings.append(
                    _finding(
                        "UNSUPPORTED_METHOD",
                        f"method {method!r} is not supported by the compiler "
                        f"(must be one of {sorted(ENDPOINT_METHODS)})",
                        True,
                    )
                )
            if not isinstance(path, str) or not path.startswith("/"):
                findings.append(
                    _finding("UNSUPPORTED_ENDPOINT_PATTERN", f"endpoint path {path!r} must start with '/'", True)
                )
        return findings

    def _regression_findings(self, execution_id: str) -> list:
        return [
            _finding(
                "SCHEMA_INCOMPATIBILITY",
                f"regression analysis: critical regression in {regression.test_id} "
                f"(expected {regression.expected}, actual {regression.actual})",
                True,
            )
            for regression in self._regression_service.regressions(execution_id)
            if regression.severity == REGRESSION_CRITICAL
        ]

    def _security_findings(self, execution_id: str) -> list:
        findings = []
        for finding in self._security_service.findings(execution_id):
            if finding.severity != SECURITY_CRITICAL:
                continue
            category = (
                "IMPORT_INCOMPATIBILITY" if finding.category == SECURITY_DEPENDENCY else "SECURITY_INCOMPATIBILITY"
            )
            findings.append(_finding(category, f"security review: {finding.evidence}", True))
        return findings

    @staticmethod
    def _build_prompt(output: dict) -> str:
        return json.dumps({"output": output})

    @staticmethod
    def _parse_response(raw_content: str):
        try:
            parsed = json.loads(raw_content)
        except (TypeError, ValueError) as exc:
            raise MalformedCompatibilityResponseError(f"LLM response is not valid JSON: {exc}")

        if not isinstance(parsed, dict) or not isinstance(parsed.get("findings"), list):
            raise MalformedCompatibilityResponseError("LLM response must be a JSON object with a 'findings' list")

        findings = parsed["findings"]
        for finding in findings:
            if not isinstance(finding, dict):
                raise MalformedCompatibilityResponseError("each finding must be an object")
            for key in ("category", "message", "blocking"):
                if key not in finding:
                    raise MalformedCompatibilityResponseError(f"finding missing required field {key!r}")
            if finding["category"] not in _LLM_CATEGORIES:
                raise MalformedCompatibilityResponseError(
                    f"finding 'category' must be one of {sorted(_LLM_CATEGORIES)}"
                )
            if not isinstance(finding["message"], str) or not finding["message"].strip():
                raise MalformedCompatibilityResponseError("finding 'message' must be a non-empty string")
            if not isinstance(finding["blocking"], bool):
                raise MalformedCompatibilityResponseError("finding 'blocking' must be a boolean")

        if "confidence" not in parsed:
            raise MalformedCompatibilityResponseError("LLM response missing required field 'confidence'")
        confidence = parsed["confidence"]
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
            raise MalformedCompatibilityResponseError("'confidence' must be a number")
        if not (0.0 <= float(confidence) <= 1.0):
            raise MalformedCompatibilityResponseError("'confidence' must be between 0.0 and 1.0")

        return findings, float(confidence)

    def review(self, execution_id: str) -> LLMCodePatchCompatibility:
        if not self._verification_service.syntax(execution_id):
            raise UnverifiedPatchError(f"execution {execution_id!r} has not passed syntax verification")

        output = self._resolve_output(execution_id)

        findings = []
        findings.extend(self._route_findings(output))
        findings.extend(self._regression_findings(execution_id))
        findings.extend(self._security_findings(execution_id))

        self._request_counter += 1
        request_id = f"patch-compatibility-{execution_id}-{self._request_counter}"

        self._context_service.create(request_id, system=COMPATIBILITY_SYSTEM_PROMPT)
        self._context_service.add(
            request_id, LLMContextItem(type="user", content=self._build_prompt(output), priority=1)
        )

        response, decision = self._orchestration_service.execute(
            self._route_request, request_id, request_id, temperature=0.0
        )

        if response is None:
            raise MalformedCompatibilityResponseError(f"LLM request failed: {decision.reason}")

        llm_findings, confidence = self._parse_response(response.content)
        findings.extend(llm_findings)

        compatible = not any(finding["blocking"] for finding in findings)

        self._review_counter += 1
        review = LLMCodePatchCompatibility(
            review_id=f"patch-compatibility-{execution_id}-{self._review_counter}",
            execution_id=execution_id,
            compatible=compatible,
            findings=findings,
            confidence=confidence,
            reviewed_at=datetime.now(timezone.utc),
        )
        self._reviews[execution_id] = review
        return review

    def _get(self, execution_id: str) -> LLMCodePatchCompatibility:
        try:
            return self._reviews[execution_id]
        except KeyError:
            raise UnknownCompatibilityReviewError(execution_id)

    def findings(self, execution_id: str) -> list:
        return list(self._get(execution_id).findings)

    def compatible(self, execution_id: str) -> bool:
        return self._get(execution_id).compatible
