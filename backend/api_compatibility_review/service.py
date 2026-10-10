import json
from datetime import datetime, timezone

from backend.api_candidates import LLMAPICandidateService
from backend.api_exposure_recommendations import LLMAPIExposureRecommendation, LLMAPIExposureService
from backend.api_risk_analysis import DEPENDENCY as RISK_DEPENDENCY
from backend.api_risk_analysis import CRITICAL as RISK_CRITICAL
from backend.api_risk_analysis import LLMAPIRiskService
from backend.api_schema_review import APPROVED, LLMAPISchemaReviewService, UnknownReviewError
from backend.api_security_review import CRITICAL as SECURITY_CRITICAL
from backend.api_security_review import LLMAPISecurityService
from backend.compilation_plan import ENDPOINT_METHODS
from backend.input_schema import LLMInputSchemaService, UnknownSchemaError
from backend.llm.context import LLMContextItem
from backend.llm.routing import LLMRouteRequest
from backend.output_schema import LLMOutputSchemaService, UnknownOutputSchemaError

from .models import LLMAPICompatibilityReview

_LLM_CATEGORIES = frozenset({"GENERATED_STRUCTURE", "SCHEMA_INCOMPATIBILITY", "DEPENDENCY_INCOMPATIBILITY"})


class MalformedCompatibilityResponseError(ValueError):
    """Raised when the LLM's compatibility response isn't well-formed."""


class MissingCandidateError(ValueError):
    """Raised when review() is called for a recommendation whose function was
    never registered as an API candidate."""


COMPATIBILITY_SYSTEM_PROMPT = (
    "You are a compiler compatibility reviewer performing a final check "
    "before a recommendation may be approved for compilation. You are "
    "given the function's method/endpoint and its already-inferred "
    "input/output schema. The existing compiler generates a Pydantic "
    "request model from the input schema's types/required/defaults, and a "
    "Pydantic response model from the output schema's types/nullable/"
    "structure -- identify anything about this schema the compiler's own "
    "generation approach could not actually handle. Respond with ONLY a "
    "single JSON object -- no prose, no markdown fencing -- of the form "
    "{\"findings\": [...], \"confidence\": 0.0}. 'findings' may be an "
    "empty list if nothing stands out. Each finding is an object with: "
    "'category' (one of GENERATED_STRUCTURE, SCHEMA_INCOMPATIBILITY, "
    "DEPENDENCY_INCOMPATIBILITY), 'message' (why this is a problem), and "
    "'blocking' (true if compilation must not proceed until fixed, false "
    "if advisory). 'confidence' is a number between 0.0 and 1.0 for the "
    "review as a whole."
)


def _finding(category: str, message: str, blocking: bool) -> dict:
    return {"category": category, "message": message, "blocking": blocking}


class LLMAPICompatibilityService:
    """The final compiler-compatibility gate for a Commit #4 recommendation.

    Reuses backend.compilation_plan.ENDPOINT_METHODS (the same HTTP methods
    the existing deterministic compiler already supports) for its own
    method/pattern check, Commit #5's schema review for schema and
    generated-structure incompatibilities, and Commit #8/#10's risk and
    security findings for dependency/security incompatibilities -- this
    service never recomputes any of those, it only aggregates them. The
    LLM (same orchestration pipeline used throughout) is only asked about
    the existing compiler's own generation approach, and every finding it
    proposes must fall in a real category. review() never writes to the
    recommendation, the schemas, the notebook, or the compiler.
    """

    def __init__(
        self,
        exposure_service: LLMAPIExposureService,
        schema_review_service: LLMAPISchemaReviewService,
        risk_service: LLMAPIRiskService,
        security_service: LLMAPISecurityService,
        api_candidate_service: LLMAPICandidateService,
        input_schema_service: LLMInputSchemaService,
        output_schema_service: LLMOutputSchemaService,
        orchestration_service,
        context_service,
        route_request: LLMRouteRequest = None,
    ):
        self._exposure_service = exposure_service
        self._schema_review_service = schema_review_service
        self._risk_service = risk_service
        self._security_service = security_service
        self._api_candidate_service = api_candidate_service
        self._input_schema_service = input_schema_service
        self._output_schema_service = output_schema_service
        self._orchestration_service = orchestration_service
        self._context_service = context_service
        self._route_request = route_request or LLMRouteRequest(
            task="api_compatibility_review", required_capabilities=["chat"]
        )
        self._reviews_by_endpoint = {}
        self._request_counter = 0
        self._review_counter = 0

    @staticmethod
    def _method_findings(recommendation: LLMAPIExposureRecommendation) -> list:
        findings = []
        if recommendation.method not in ENDPOINT_METHODS:
            findings.append(
                _finding(
                    "UNSUPPORTED_METHOD",
                    f"method {recommendation.method!r} is not supported by the compiler "
                    f"(must be one of {sorted(ENDPOINT_METHODS)})",
                    True,
                )
            )
        if not recommendation.endpoint_name.startswith("/"):
            findings.append(
                _finding(
                    "UNSUPPORTED_ENDPOINT_PATTERN",
                    f"endpoint_name {recommendation.endpoint_name!r} must start with '/'",
                    True,
                )
            )
        return findings

    def _schema_findings(self, recommendation: LLMAPIExposureRecommendation) -> list:
        try:
            review = self._schema_review_service.review_for(recommendation.recommendation_id)
        except UnknownReviewError:
            return [_finding("SCHEMA_INCOMPATIBILITY", "recommendation has not been schema-reviewed yet", True)]

        if review.status != APPROVED:
            return [
                _finding(
                    "SCHEMA_INCOMPATIBILITY", f"schema review is {review.status}, not {APPROVED}", True
                )
            ]

        return [
            _finding("SCHEMA_INCOMPATIBILITY", f"schema review: {f['message']}", f["blocking"])
            for f in review.findings
        ]

    def _dependency_findings(self, endpoint: str) -> list:
        return [
            _finding(
                "DEPENDENCY_INCOMPATIBILITY", f"risk analysis: {f.evidence}", f.severity == RISK_CRITICAL
            )
            for f in self._risk_service.findings(endpoint)
            if f.category == RISK_DEPENDENCY
        ]

    def _security_findings(self, endpoint: str) -> list:
        return [
            _finding("SECURITY_INCOMPATIBILITY", f"security review: {f.evidence}", True)
            for f in self._security_service.findings(endpoint)
            if f.severity == SECURITY_CRITICAL
        ]

    @staticmethod
    def _build_prompt(recommendation: LLMAPIExposureRecommendation, input_schema, output_schema) -> str:
        payload = {
            "function_name": recommendation.function_name,
            "method": recommendation.method,
            "endpoint_name": recommendation.endpoint_name,
            "input": {"types": input_schema.types, "required": input_schema.required, "defaults": input_schema.defaults},
            "output": {"types": output_schema.types, "nullable": output_schema.nullable, "structure": output_schema.structure},
        }
        return json.dumps(payload)

    @staticmethod
    def _parse_response(raw_content: str) -> list:
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

    def review(self, recommendation: LLMAPIExposureRecommendation) -> LLMAPICompatibilityReview:
        notebook_id = self._exposure_service.notebook_id_for(recommendation.recommendation_id)
        candidate = next(
            (
                c
                for c in self._api_candidate_service.candidates(notebook_id)
                if c.function_name == recommendation.function_name
            ),
            None,
        )
        if candidate is None:
            raise MissingCandidateError(
                f"function {recommendation.function_name!r} was never registered as an API candidate"
            )

        endpoint = f"{recommendation.method} {recommendation.endpoint_name}"

        findings = []
        findings.extend(self._method_findings(recommendation))
        findings.extend(self._schema_findings(recommendation))
        findings.extend(self._dependency_findings(endpoint))
        findings.extend(self._security_findings(endpoint))

        try:
            input_schema = self._input_schema_service.get(candidate.candidate_id)
            output_schema = self._output_schema_service.get(candidate.candidate_id)
        except (UnknownSchemaError, UnknownOutputSchemaError):
            input_schema = output_schema = None

        self._request_counter += 1
        request_id = f"api-compatibility-{recommendation.recommendation_id}-{self._request_counter}"

        self._context_service.create(request_id, system=COMPATIBILITY_SYSTEM_PROMPT)
        if input_schema is not None and output_schema is not None:
            prompt_content = self._build_prompt(recommendation, input_schema, output_schema)
        else:
            prompt_content = json.dumps(
                {
                    "function_name": recommendation.function_name,
                    "method": recommendation.method,
                    "endpoint_name": recommendation.endpoint_name,
                }
            )
        self._context_service.add(
            request_id, LLMContextItem(type="user", content=prompt_content, priority=1)
        )

        response, decision = self._orchestration_service.execute(
            self._route_request, request_id, request_id, temperature=0.0
        )

        if response is None:
            raise MalformedCompatibilityResponseError(f"LLM request failed: {decision.reason}")

        llm_findings, confidence = self._parse_response(response.content)
        for raw_finding in llm_findings:
            findings.append(_finding(raw_finding["category"], raw_finding["message"], raw_finding["blocking"]))

        compatible = not any(f["blocking"] for f in findings)

        self._review_counter += 1
        review = LLMAPICompatibilityReview(
            review_id=f"compatibility-{recommendation.recommendation_id}-{self._review_counter}",
            endpoint=endpoint,
            compatible=compatible,
            findings=findings,
            confidence=confidence,
            reviewed_at=datetime.now(timezone.utc),
        )
        self._reviews_by_endpoint[endpoint] = review
        return review

    def findings(self, endpoint: str) -> list:
        review = self._reviews_by_endpoint.get(endpoint)
        return list(review.findings) if review else []

    def compatible(self, endpoint: str) -> bool:
        review = self._reviews_by_endpoint.get(endpoint)
        return review.compatible if review else True
