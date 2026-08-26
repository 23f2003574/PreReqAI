import json
import re

from backend.code_fix_suggestions import LLMCodeFixSuggestionService
from backend.code_patch_execution import LLMCodePatchExecutionService
from backend.code_patch_planning import LLMCodePatchService
from backend.code_patch_regression import LLMCodePatchRegressionService
from backend.code_patch_regression import CRITICAL as REGRESSION_CRITICAL
from backend.code_patch_verification import LLMCodePatchVerificationService
from backend.generated_code_review import LLMGeneratedCodeReviewService
from backend.llm.context import LLMContextItem
from backend.llm.routing import LLMRouteRequest

from .models import (
    AUTH,
    CATEGORIES,
    CRITICAL,
    DATA,
    DEPENDENCY,
    ERROR,
    INPUT,
    SECRETS,
    SEVERITIES,
    WARNING,
    LLMCodePatchSecurityFinding,
)

_MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{10,}"),
    re.compile(r"AKIA[A-Z0-9]{12,}"),
    re.compile(r"(?i)\b(api[_-]?key|token|secret|password)\s*=\s*['\"][^'\"]+['\"]"),
)

_INPUT_PATTERNS = (
    ("eval(", "eval() can execute arbitrary code from input"),
    ("exec(", "exec() can execute arbitrary code from input"),
    ("pickle.loads(", "pickle.loads() can execute arbitrary code from untrusted input"),
)

_DEPENDENCY_PATTERNS = (
    ("os.system(", "os.system() introduces an unreviewed external process dependency"),
    ("subprocess.", "subprocess usage introduces an unreviewed external process dependency"),
    ("__import__(", "dynamic __import__ introduces an unreviewed module dependency"),
)

SECURITY_SYSTEM_PROMPT = (
    "You are a security reviewer performing a final check on an already- "
    "applied patch's current generated output. You are given that output "
    "verbatim (any credential-looking value has already been redacted). "
    "Identify any additional security risks beyond what deterministic "
    "checks already caught. Respond with ONLY a single JSON object -- no "
    "prose, no markdown fencing -- of the form {\"findings\": [...]}. "
    "'findings' may be an empty list if nothing further stands out. Each "
    "finding is an object with: 'category' (one of AUTH, INPUT, SECRETS, "
    "DATA, DEPENDENCY), 'severity' (one of INFO, WARNING, ERROR, "
    "CRITICAL), 'evidence' (a specific, concrete reason grounded in the "
    "given output -- never a vague or unsupported claim, and never a "
    "literal credential value even if you believe you can reconstruct "
    "one), and 'confidence' (a number between 0.0 and 1.0)."
)


class MalformedSecurityResponseError(ValueError):
    """Raised when the LLM's security-finding response isn't well-formed."""


class UnverifiedPatchError(ValueError):
    """Raised when analyze() is called for an execution that hasn't passed Commit #6 syntax verification."""


def _redact(text: str) -> str:
    redacted = text
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def _redact_value(value):
    if isinstance(value, str):
        return _redact(value)
    if isinstance(value, dict):
        return {key: _redact_value(sub) for key, sub in value.items()}
    if isinstance(value, list):
        return [_redact_value(sub) for sub in value]
    return value


def _iter_strings(value, prefix: str = ""):
    if isinstance(value, dict):
        for key, sub in value.items():
            yield from _iter_strings(sub, f"{prefix}.{key}" if prefix else str(key))
    elif isinstance(value, list):
        for index, sub in enumerate(value):
            yield from _iter_strings(sub, f"{prefix}[{index}]")
    elif isinstance(value, str):
        yield prefix, value


def _secrets_findings(strings: list) -> list:
    findings = []
    for location, value in strings:
        for pattern in _SECRET_PATTERNS:
            if pattern.search(value):
                findings.append(
                    (SECRETS, CRITICAL, f"hardcoded credential pattern matched in generated output at {location!r}")
                )
    return findings


def _auth_findings(output: dict) -> list:
    endpoints = output.get("endpoints")
    if not isinstance(endpoints, list):
        return []
    findings = []
    for endpoint in endpoints:
        if not isinstance(endpoint, dict):
            continue
        method = endpoint.get("method")
        severity = ERROR if method in _MUTATING_METHODS else WARNING
        findings.append(
            (
                AUTH,
                severity,
                "this codebase has no authentication/authorization enforcement mechanism for generated "
                f"API endpoints; {method} {endpoint.get('path')} would be unauthenticated if compiled",
            )
        )
    return findings


def _input_findings(strings: list) -> list:
    findings = []
    for location, value in strings:
        for pattern, message in _INPUT_PATTERNS:
            if pattern in value:
                findings.append((INPUT, CRITICAL, f"generated output at {location!r} uses {pattern.rstrip('(')}: {message}"))
    return findings


def _dependency_findings(strings: list) -> list:
    findings = []
    for location, value in strings:
        for pattern, message in _DEPENDENCY_PATTERNS:
            if pattern in value:
                findings.append(
                    (
                        DEPENDENCY,
                        CRITICAL,
                        f"generated output at {location!r} uses {pattern.rstrip('(').rstrip('.')}: {message}",
                    )
                )
    return findings


class LLMCodePatchSecurityService:
    """Reviews an applied Commit #5 patch's current generated output for
    security regressions, before it may be accepted.

    Reuses Commit #6's LLMCodePatchVerificationService.syntax() as the sole
    gate -- analyze() never reviews an execution that hasn't passed syntax
    verification -- and Commit #7's LLMCodePatchRegressionService.regressions()
    as the sole source of behavioral-regression evidence: any CRITICAL
    regression becomes a DATA finding here, never recomputed independently.
    The same deterministic secret/dangerous-construct pattern scan
    backend.api_security_review and backend.generated_code_review already
    use covers SECRETS/INPUT/DEPENDENCY, and the same "no authentication
    mechanism exists" fact backend.api_security_review already establishes
    covers AUTH when the current output describes endpoints. The LLM (same
    orchestration pipeline used throughout) is only asked for additional
    risks beyond those, and every finding's evidence -- deterministic or
    LLM-proposed -- is redacted of anything matching a secret pattern
    before it is ever stored, sent to the LLM, or returned, so a finding
    can never itself leak the credential it flags. analyze() never mutates
    the generated output, the execution, or anything upstream of it.
    """

    def __init__(
        self,
        verification_service: LLMCodePatchVerificationService,
        regression_service: LLMCodePatchRegressionService,
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
        self._execution_service = execution_service
        self._patch_service = patch_service
        self._fix_service = fix_service
        self._review_service = review_service
        self._orchestration_service = orchestration_service
        self._context_service = context_service
        self._route_request = route_request or LLMRouteRequest(
            task="code_patch_security_review", required_capabilities=["chat"]
        )
        self._findings_by_execution = {}
        self._request_counter = 0
        self._finding_counter = 0

    def _resolve_output(self, execution_id: str) -> dict:
        execution = self._execution_service.get(execution_id)
        plan = self._patch_service.get(execution.plan_id)
        suggestion = self._fix_service.get(plan.suggestion_id)
        review = self._review_service.get(suggestion.review_id)
        return self._review_service.get_generated_output(review.target).output

    def _make_finding(self, execution_id: str, category: str, severity: str, evidence: str, confidence: float):
        self._finding_counter += 1
        return LLMCodePatchSecurityFinding(
            finding_id=f"patch-security-{execution_id}-{self._finding_counter}",
            execution_id=execution_id,
            category=category,
            severity=severity,
            evidence=_redact(evidence),
            confidence=confidence,
        )

    def _regression_findings(self, execution_id: str) -> list:
        return [
            (
                DATA,
                CRITICAL,
                f"Commit #7 regression analysis found a critical regression in {regression.test_id}: "
                f"expected {regression.expected}, actual {regression.actual}",
            )
            for regression in self._regression_service.regressions(execution_id)
            if regression.severity == REGRESSION_CRITICAL
        ]

    @staticmethod
    def _build_prompt(output: dict) -> str:
        return json.dumps({"output": _redact_value(output)})

    @staticmethod
    def _parse_response(raw_content: str) -> list:
        try:
            parsed = json.loads(raw_content)
        except (TypeError, ValueError) as exc:
            raise MalformedSecurityResponseError(f"LLM response is not valid JSON: {exc}")

        if not isinstance(parsed, dict) or not isinstance(parsed.get("findings"), list):
            raise MalformedSecurityResponseError("LLM response must be a JSON object with a 'findings' list")

        findings = parsed["findings"]
        for finding in findings:
            if not isinstance(finding, dict):
                raise MalformedSecurityResponseError("each finding must be an object")
            for key in ("category", "severity", "evidence", "confidence"):
                if key not in finding:
                    raise MalformedSecurityResponseError(f"finding missing required field {key!r}")
            if finding["category"] not in CATEGORIES:
                raise MalformedSecurityResponseError(f"finding 'category' must be one of {sorted(CATEGORIES)}")
            if finding["severity"] not in SEVERITIES:
                raise MalformedSecurityResponseError(f"finding 'severity' must be one of {sorted(SEVERITIES)}")
            if not isinstance(finding["evidence"], str) or not finding["evidence"].strip():
                raise MalformedSecurityResponseError(
                    "finding 'evidence' must be non-empty -- every finding requires evidence"
                )
            confidence = finding["confidence"]
            if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
                raise MalformedSecurityResponseError("finding 'confidence' must be a number")
            if not (0.0 <= float(confidence) <= 1.0):
                raise MalformedSecurityResponseError("finding 'confidence' must be between 0.0 and 1.0")

        return findings

    def analyze(self, execution_id: str) -> list:
        if not self._verification_service.syntax(execution_id):
            raise UnverifiedPatchError(f"execution {execution_id!r} has not passed syntax verification")

        output = self._resolve_output(execution_id)
        strings = list(_iter_strings(output))

        raw_findings = []
        raw_findings.extend(_secrets_findings(strings))
        raw_findings.extend(_auth_findings(output))
        raw_findings.extend(_input_findings(strings))
        raw_findings.extend(_dependency_findings(strings))
        raw_findings.extend(self._regression_findings(execution_id))

        findings = [
            self._make_finding(execution_id, category, severity, evidence, 1.0)
            for category, severity, evidence in raw_findings
        ]

        self._request_counter += 1
        request_id = f"patch-security-{execution_id}-{self._request_counter}"

        self._context_service.create(request_id, system=SECURITY_SYSTEM_PROMPT)
        self._context_service.add(
            request_id, LLMContextItem(type="user", content=self._build_prompt(output), priority=1)
        )

        response, decision = self._orchestration_service.execute(
            self._route_request, request_id, request_id, temperature=0.0
        )

        if response is None:
            raise MalformedSecurityResponseError(f"LLM request failed: {decision.reason}")

        for raw_finding in self._parse_response(response.content):
            findings.append(
                self._make_finding(
                    execution_id,
                    raw_finding["category"],
                    raw_finding["severity"],
                    raw_finding["evidence"],
                    float(raw_finding["confidence"]),
                )
            )

        self._findings_by_execution.setdefault(execution_id, []).extend(findings)
        return findings

    def findings(self, execution_id: str) -> list:
        return list(self._findings_by_execution.get(execution_id, []))

    def blocking(self, execution_id: str) -> bool:
        return any(finding.severity == CRITICAL for finding in self.findings(execution_id))
