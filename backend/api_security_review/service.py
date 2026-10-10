import json
import re

from backend.api_candidates import LLMAPICandidateService
from backend.api_exposure_recommendations import LLMAPIExposureRecommendation, LLMAPIExposureService
from backend.api_schema_review import LLMAPISchemaReviewService, UnknownReviewError
from backend.llm.context import LLMContextItem
from backend.llm.routing import LLMRouteRequest
from backend.notebook_analysis import LLMNotebookAnalysisService
from backend.notebook_dependencies import DATA as DEP_DATA
from backend.notebook_dependencies import MODEL as DEP_MODEL
from backend.notebook_dependencies import LLMNotebookDependencyService

from .models import (
    AUTH,
    CATEGORIES,
    CODE,
    CRITICAL,
    DATA,
    ERROR,
    INPUT,
    SECRETS,
    SEVERITIES,
    WARNING,
    LLMAPISecurityFinding,
)


class MalformedSecurityResponseError(ValueError):
    """Raised when the LLM's security-finding response isn't well-formed."""


class MissingCandidateError(ValueError):
    """Raised when analyze() is called for a recommendation whose function was
    never registered as an API candidate."""


_MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

_DANGEROUS_PATTERNS = (
    ("eval(", "eval() can execute arbitrary code"),
    ("exec(", "exec() can execute arbitrary code"),
    ("os.system(", "os.system() can execute arbitrary shell commands"),
    ("subprocess.", "subprocess usage can execute arbitrary shell commands"),
    ("pickle.loads(", "pickle.loads() can execute arbitrary code from untrusted input"),
    ("__import__(", "dynamic __import__ can load arbitrary modules"),
)

_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{10,}"),
    re.compile(r"AKIA[A-Z0-9]{12,}"),
    re.compile(r"(?i)\b(api[_-]?key|token|secret|password)\s*=\s*['\"][^'\"]+['\"]"),
)

SECURITY_SYSTEM_PROMPT = (
    "You are an API security reviewer performing a final check before a "
    "recommendation may be compiled into a real endpoint. You are given "
    "the function's source and its already-inferred input/output schemas. "
    "Identify any additional security risks beyond what deterministic "
    "checks already caught -- e.g. injection risks, unsafe deserialization, "
    "or unvalidated data reaching a sensitive sink. Respond with ONLY a "
    "single JSON object -- no prose, no markdown fencing -- of the form "
    "{\"findings\": [...]}. 'findings' may be an empty list if nothing "
    "further stands out. Each finding is an object with: 'category' (one "
    "of INPUT, AUTH, SECRETS, DATA, CODE), 'severity' (one of INFO, "
    "WARNING, ERROR, CRITICAL), 'evidence' (a specific, concrete reason "
    "grounded in the given source or schema -- never a vague or "
    "unsupported claim), and 'confidence' (a number between 0.0 and 1.0)."
)


class LLMAPISecurityService:
    """Identifies security risks in a Commit #4 recommendation before it may be compiled.

    Reuses Commit #5's schema review findings (an ambiguous or conflicting
    input schema is itself an INPUT validation risk), the verified absence
    of any endpoint authentication mechanism in this codebase (AUTH),
    backend.notebook_dependencies' real DATA/MODEL edges (DATA), and a
    static pattern-scan of the function's own already-extracted source
    (backend.notebook_analysis) for hardcoded secrets (SECRETS) and
    dangerous constructs (CODE) -- all deterministic, all grounded in real
    evidence. The LLM (same orchestration pipeline used throughout) is only
    asked for additional risks beyond those, and every finding it proposes
    must include concrete evidence. This service never writes to the
    recommendation, the schemas, the notebook, or the compiler -- analyze()
    only ever reads them.
    """

    def __init__(
        self,
        exposure_service: LLMAPIExposureService,
        schema_review_service: LLMAPISchemaReviewService,
        api_candidate_service: LLMAPICandidateService,
        notebook_analysis_service: LLMNotebookAnalysisService,
        dependency_service: LLMNotebookDependencyService,
        orchestration_service,
        context_service,
        route_request: LLMRouteRequest = None,
    ):
        self._exposure_service = exposure_service
        self._schema_review_service = schema_review_service
        self._api_candidate_service = api_candidate_service
        self._notebook_analysis_service = notebook_analysis_service
        self._dependency_service = dependency_service
        self._orchestration_service = orchestration_service
        self._context_service = context_service
        self._route_request = route_request or LLMRouteRequest(
            task="api_security_review", required_capabilities=["chat"]
        )
        self._findings_by_endpoint = {}
        self._request_counter = 0
        self._finding_counter = 0

    def _make_finding(self, endpoint: str, category: str, severity: str, evidence: str, confidence: float):
        self._finding_counter += 1
        return LLMAPISecurityFinding(
            finding_id=f"security-{endpoint}-{self._finding_counter}".replace(" ", "-"),
            endpoint=endpoint,
            category=category,
            severity=severity,
            evidence=evidence,
            confidence=confidence,
        )

    def _schema_review_findings(self, recommendation: LLMAPIExposureRecommendation, endpoint: str) -> list:
        try:
            review = self._schema_review_service.review_for(recommendation.recommendation_id)
        except UnknownReviewError:
            return [
                self._make_finding(
                    endpoint, INPUT, WARNING, "recommendation has not been schema-reviewed yet", 1.0
                )
            ]

        return [
            self._make_finding(
                endpoint,
                INPUT,
                CRITICAL if finding["blocking"] else WARNING,
                f"schema review: {finding['message']}",
                review.confidence,
            )
            for finding in review.findings
        ]

    def _auth_finding(self, recommendation: LLMAPIExposureRecommendation, endpoint: str):
        severity = ERROR if recommendation.method in _MUTATING_METHODS else WARNING
        return self._make_finding(
            endpoint,
            AUTH,
            severity,
            "this codebase has no authentication/authorization enforcement mechanism for "
            f"generated API endpoints; {recommendation.method} {recommendation.endpoint_name} "
            "would be unauthenticated if compiled",
            1.0,
        )

    def _secrets_findings(self, source: str, endpoint: str) -> list:
        findings = []
        for pattern in _SECRET_PATTERNS:
            match = pattern.search(source)
            if match:
                findings.append(
                    self._make_finding(
                        endpoint,
                        SECRETS,
                        CRITICAL,
                        f"source appears to contain a hardcoded credential: {match.group(0)[:40]!r}",
                        1.0,
                    )
                )
        return findings

    def _data_findings(self, recommendation: LLMAPIExposureRecommendation, notebook_id: str, endpoint: str) -> list:
        node_id = f"{notebook_id}::function:{recommendation.function_name}"
        sensitive_deps = [
            dep for dep in self._dependency_service.upstream(node_id) if dep.dependency_type in (DEP_DATA, DEP_MODEL)
        ]
        if not sensitive_deps:
            return []

        labels = sorted({dep.source.rsplit(":", 1)[-1] for dep in sensitive_deps})
        return [
            self._make_finding(
                endpoint,
                DATA,
                WARNING,
                f"endpoint output may be derived from external data/model source(s): {labels}",
                1.0,
            )
        ]

    def _code_findings(self, source: str, endpoint: str) -> list:
        findings = []
        for pattern, message in _DANGEROUS_PATTERNS:
            if pattern in source:
                findings.append(
                    self._make_finding(
                        endpoint, CODE, CRITICAL, f"source uses {pattern.rstrip('(').rstrip('.')}: {message}", 1.0
                    )
                )
        return findings

    @staticmethod
    def _build_prompt(recommendation: LLMAPIExposureRecommendation, source: str) -> str:
        payload = {
            "function_name": recommendation.function_name,
            "method": recommendation.method,
            "endpoint_name": recommendation.endpoint_name,
            "source": source,
        }
        return json.dumps(payload)

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

    def analyze(self, recommendation: LLMAPIExposureRecommendation) -> list:
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

        analysis = self._notebook_analysis_service.get_by_notebook(notebook_id)
        endpoint = f"{recommendation.method} {recommendation.endpoint_name}"
        function = next((fn for fn in analysis.functions if fn["name"] == recommendation.function_name), None)
        source = analysis.cells[function["cell_index"]].source if function else ""

        findings = []
        findings.extend(self._schema_review_findings(recommendation, endpoint))
        findings.append(self._auth_finding(recommendation, endpoint))
        findings.extend(self._secrets_findings(source, endpoint))
        findings.extend(self._data_findings(recommendation, notebook_id, endpoint))
        findings.extend(self._code_findings(source, endpoint))

        self._request_counter += 1
        request_id = f"api-security-{recommendation.recommendation_id}-{self._request_counter}"

        self._context_service.create(request_id, system=SECURITY_SYSTEM_PROMPT)
        self._context_service.add(
            request_id,
            LLMContextItem(type="user", content=self._build_prompt(recommendation, source), priority=1),
        )

        response, decision = self._orchestration_service.execute(
            self._route_request, request_id, request_id, temperature=0.0
        )

        if response is None:
            raise MalformedSecurityResponseError(f"LLM request failed: {decision.reason}")

        for raw_finding in self._parse_response(response.content):
            findings.append(
                self._make_finding(
                    endpoint,
                    raw_finding["category"],
                    raw_finding["severity"],
                    raw_finding["evidence"],
                    float(raw_finding["confidence"]),
                )
            )

        self._findings_by_endpoint.setdefault(endpoint, []).extend(findings)
        return findings

    def findings(self, endpoint: str) -> list:
        return list(self._findings_by_endpoint.get(endpoint, []))

    def blocking(self, endpoint: str) -> bool:
        return any(finding.severity == CRITICAL for finding in self.findings(endpoint))
