import ast
import json
import re

from backend.code_fix_suggestions import LLMCodeFixSuggestionService
from backend.code_patch_compatibility_review import LLMCodePatchCompatibilityService, UnknownCompatibilityReviewError
from backend.code_patch_execution import LLMCodePatchExecutionService
from backend.code_patch_planning import LLMCodePatchService
from backend.code_patch_regression import CRITICAL as REGRESSION_CRITICAL
from backend.code_patch_regression import LLMCodePatchRegressionService, UnknownRegressionAnalysisError
from backend.code_patch_security_review import CRITICAL as SECURITY_CRITICAL
from backend.code_patch_security_review import LLMCodePatchSecurityService
from backend.code_patch_verification import LLMCodePatchVerificationService
from backend.generated_code_review import LLMGeneratedCodeReviewService
from backend.llm.context import LLMContextItem
from backend.llm.routing import LLMRouteRequest

from .models import (
    CATEGORIES,
    COMPLEXITY,
    CRITICAL,
    DEAD_CODE,
    DUPLICATION,
    ERROR,
    INFO,
    MAINTAINABILITY,
    SEVERITIES,
    STYLE,
    WARNING,
    LLMCodePatchQualityFinding,
)

_SNAKE_CASE_RE = re.compile(r"^[a-z_][a-z0-9_]*$")
_COMPLEXITY_THRESHOLD = 5
_MAX_FUNCTION_LINES = 30

QUALITY_SYSTEM_PROMPT = (
    "You are a code-quality reviewer performing a final check on an "
    "already-applied patch's current generated output. You are given that "
    "output verbatim. Identify any additional maintainability concerns "
    "beyond what deterministic checks already caught. Respond with ONLY a "
    "single JSON object -- no prose, no markdown fencing -- of the form "
    "{\"findings\": [...]}. 'findings' may be an empty list if nothing "
    "further stands out. Each finding is an object with: 'category' (one "
    "of STYLE, COMPLEXITY, DUPLICATION, MAINTAINABILITY, DEAD_CODE), "
    "'severity' (one of INFO, WARNING, ERROR, CRITICAL), 'location' (the "
    "exact key path into the given output this finding is about -- taken "
    "only from the paths listed in 'valid_locations', never invented), "
    "'evidence' (a specific, concrete reason grounded in the given "
    "output -- never a vague or unsupported claim), and 'confidence' (a "
    "number between 0.0 and 1.0)."
)


class MalformedQualityResponseError(ValueError):
    """Raised when the LLM's quality-finding response isn't well-formed."""


class UnverifiedPatchError(ValueError):
    """Raised when analyze() is called for an execution that hasn't passed Commit #6 syntax verification."""


def _flatten_locations(output: dict) -> set:
    locations = set()

    def walk(value, prefix):
        if isinstance(value, dict):
            for key, sub in value.items():
                path = f"{prefix}.{key}" if prefix else str(key)
                locations.add(path)
                walk(sub, path)
        elif isinstance(value, list):
            for index, sub in enumerate(value):
                path = f"{prefix}[{index}]"
                locations.add(path)
                walk(sub, path)

    walk(output, "")
    return locations


def _functions(tree: ast.Module) -> list:
    return [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]


def _style_findings(tree: ast.Module) -> list:
    return [
        (STYLE, WARNING, f"function {function.name!r} is not snake_case", "source")
        for function in _functions(tree)
        if not _SNAKE_CASE_RE.match(function.name)
    ]


def _complexity_findings(tree: ast.Module) -> list:
    findings = []
    for function in _functions(tree):
        decision_points = 1 + sum(
            1
            for node in ast.walk(function)
            if isinstance(node, (ast.If, ast.For, ast.While, ast.ExceptHandler, ast.BoolOp))
        )
        if decision_points > _COMPLEXITY_THRESHOLD:
            findings.append(
                (
                    COMPLEXITY,
                    WARNING,
                    f"function {function.name!r} has cyclomatic complexity ~{decision_points}, above the "
                    f"{_COMPLEXITY_THRESHOLD} threshold",
                    "source",
                )
            )
    return findings


def _duplication_findings(tree: ast.Module) -> list:
    findings = []
    seen = {}
    for function in _functions(tree):
        body_dump = ast.dump(ast.Module(body=function.body, type_ignores=[]))
        if body_dump in seen:
            findings.append(
                (DUPLICATION, WARNING, f"function {function.name!r} has an identical body to {seen[body_dump]!r}", "source")
            )
        else:
            seen[body_dump] = function.name
    return findings


def _maintainability_findings(tree: ast.Module) -> list:
    findings = []
    for function in _functions(tree):
        if ast.get_docstring(function) is None:
            findings.append((MAINTAINABILITY, INFO, f"function {function.name!r} has no docstring", "source"))
        if function.end_lineno is not None:
            line_count = function.end_lineno - function.lineno + 1
            if line_count > _MAX_FUNCTION_LINES:
                findings.append(
                    (
                        MAINTAINABILITY,
                        WARNING,
                        f"function {function.name!r} is {line_count} lines, above the {_MAX_FUNCTION_LINES}-line "
                        "threshold",
                        "source",
                    )
                )
    return findings


def _dead_code_findings(tree: ast.Module) -> list:
    findings = []
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(body, list):
            continue
        for stmt in body[:-1]:
            if isinstance(stmt, (ast.Return, ast.Raise, ast.Continue, ast.Break)):
                findings.append(
                    (DEAD_CODE, WARNING, f"unreachable code after a {type(stmt).__name__} at line {stmt.lineno}", "source")
                )
    return findings


class LLMCodePatchQualityService:
    """Assesses maintainability/code-quality regressions in an applied
    Commit #5 patch's current generated output, before it may be accepted.

    Reuses Commit #6's LLMCodePatchVerificationService.syntax() as the sole
    gate, and folds Commit #7's regressions, Commit #8's security findings,
    and Commit #9's compatibility findings straight through as
    MAINTAINABILITY evidence -- this service never recomputes any of them,
    and never fails analyze() just because one of them hasn't been run yet
    (the same "quality has no mandatory prerequisite" philosophy
    backend.transformation_gate already uses). Its own deterministic checks
    parse the current output's own "source" via `ast` -- the same
    source-inspection convention used throughout this codebase -- for
    non-snake_case names (STYLE), high branching (COMPLEXITY), duplicate
    function bodies (DUPLICATION), missing docstrings/oversized functions
    (MAINTAINABILITY), and unreachable statements (DEAD_CODE); no external
    linter or static-analysis library is introduced. The LLM (same
    orchestration pipeline used throughout) is only asked for additional
    concerns, and every finding it proposes must cite a real location in
    the current output. analyze() never mutates the generated output, the
    execution, or anything upstream of it.
    """

    def __init__(
        self,
        verification_service: LLMCodePatchVerificationService,
        regression_service: LLMCodePatchRegressionService,
        security_service: LLMCodePatchSecurityService,
        compatibility_service: LLMCodePatchCompatibilityService,
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
        self._compatibility_service = compatibility_service
        self._execution_service = execution_service
        self._patch_service = patch_service
        self._fix_service = fix_service
        self._review_service = review_service
        self._orchestration_service = orchestration_service
        self._context_service = context_service
        self._route_request = route_request or LLMRouteRequest(
            task="code_patch_quality_review", required_capabilities=["chat"]
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
        return LLMCodePatchQualityFinding(
            finding_id=f"patch-quality-{execution_id}-{self._finding_counter}",
            execution_id=execution_id,
            category=category,
            severity=severity,
            evidence=evidence,
            confidence=confidence,
        )

    def _source_findings(self, output: dict) -> list:
        source = output.get("source")
        if not isinstance(source, str):
            return []
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return []

        findings = []
        findings.extend(_style_findings(tree))
        findings.extend(_complexity_findings(tree))
        findings.extend(_duplication_findings(tree))
        findings.extend(_maintainability_findings(tree))
        findings.extend(_dead_code_findings(tree))
        return findings

    def _regression_findings(self, execution_id: str) -> list:
        try:
            regressions = self._regression_service.regressions(execution_id)
        except UnknownRegressionAnalysisError:
            return []
        return [
            (
                MAINTAINABILITY,
                CRITICAL if regression.severity == REGRESSION_CRITICAL else WARNING,
                f"regression analysis found a {regression.severity} regression in {regression.test_id}",
                "source",
            )
            for regression in regressions
        ]

    def _security_findings(self, execution_id: str) -> list:
        return [
            (
                MAINTAINABILITY,
                CRITICAL if finding.severity == SECURITY_CRITICAL else WARNING,
                f"security review flagged a {finding.category} concern that also affects maintainability: "
                f"{finding.evidence}",
                "source",
            )
            for finding in self._security_service.findings(execution_id)
        ]

    def _compatibility_findings(self, execution_id: str) -> list:
        try:
            findings = self._compatibility_service.findings(execution_id)
        except UnknownCompatibilityReviewError:
            return []
        return [
            (
                MAINTAINABILITY,
                ERROR if finding["blocking"] else WARNING,
                f"compatibility review flagged {finding['category']}: {finding['message']}",
                "source",
            )
            for finding in findings
        ]

    @staticmethod
    def _build_prompt(output: dict, valid_locations: set) -> str:
        return json.dumps({"output": output, "valid_locations": sorted(valid_locations)})

    @staticmethod
    def _parse_response(raw_content: str, valid_locations: set) -> list:
        try:
            parsed = json.loads(raw_content)
        except (TypeError, ValueError) as exc:
            raise MalformedQualityResponseError(f"LLM response is not valid JSON: {exc}")

        if not isinstance(parsed, dict) or not isinstance(parsed.get("findings"), list):
            raise MalformedQualityResponseError("LLM response must be a JSON object with a 'findings' list")

        findings = parsed["findings"]
        for finding in findings:
            if not isinstance(finding, dict):
                raise MalformedQualityResponseError("each finding must be an object")
            for key in ("category", "severity", "location", "evidence", "confidence"):
                if key not in finding:
                    raise MalformedQualityResponseError(f"finding missing required field {key!r}")
            if finding["category"] not in CATEGORIES:
                raise MalformedQualityResponseError(f"finding 'category' must be one of {sorted(CATEGORIES)}")
            if finding["severity"] not in SEVERITIES:
                raise MalformedQualityResponseError(f"finding 'severity' must be one of {sorted(SEVERITIES)}")
            if not isinstance(finding["location"], str) or finding["location"] not in valid_locations:
                raise MalformedQualityResponseError(
                    f"finding location {finding.get('location')!r} does not reference real generated output"
                )
            if not isinstance(finding["evidence"], str) or not finding["evidence"].strip():
                raise MalformedQualityResponseError(
                    "finding 'evidence' must be non-empty -- every finding requires evidence"
                )
            confidence = finding["confidence"]
            if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
                raise MalformedQualityResponseError("finding 'confidence' must be a number")
            if not (0.0 <= float(confidence) <= 1.0):
                raise MalformedQualityResponseError("finding 'confidence' must be between 0.0 and 1.0")

        return findings

    def analyze(self, execution_id: str) -> list:
        if not self._verification_service.syntax(execution_id):
            raise UnverifiedPatchError(f"execution {execution_id!r} has not passed syntax verification")

        output = self._resolve_output(execution_id)

        raw_findings = []
        raw_findings.extend(self._source_findings(output))
        raw_findings.extend(self._regression_findings(execution_id))
        raw_findings.extend(self._security_findings(execution_id))
        raw_findings.extend(self._compatibility_findings(execution_id))

        findings = [
            self._make_finding(execution_id, category, severity, evidence, 1.0)
            for category, severity, evidence, _location in raw_findings
        ]

        valid_locations = _flatten_locations(output)

        self._request_counter += 1
        request_id = f"patch-quality-{execution_id}-{self._request_counter}"

        self._context_service.create(request_id, system=QUALITY_SYSTEM_PROMPT)
        self._context_service.add(
            request_id,
            LLMContextItem(type="user", content=self._build_prompt(output, valid_locations), priority=1),
        )

        response, decision = self._orchestration_service.execute(
            self._route_request, request_id, request_id, temperature=0.0
        )

        if response is None:
            raise MalformedQualityResponseError(f"LLM request failed: {decision.reason}")

        for raw_finding in self._parse_response(response.content, valid_locations):
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
