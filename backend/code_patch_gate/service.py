from datetime import datetime, timezone

from backend.code_patch_compatibility_review import LLMCodePatchCompatibilityService, UnknownCompatibilityReviewError
from backend.code_patch_quality_review import CRITICAL as QUALITY_CRITICAL
from backend.code_patch_quality_review import LLMCodePatchQualityService
from backend.code_patch_regression import CRITICAL as REGRESSION_CRITICAL
from backend.code_patch_regression import LLMCodePatchRegressionService, UnknownRegressionAnalysisError
from backend.code_patch_security_review import CRITICAL as SECURITY_CRITICAL
from backend.code_patch_security_review import LLMCodePatchSecurityService
from backend.code_patch_verification import LLMCodePatchVerificationService, UnknownPatchVerificationError

from .models import COMPATIBILITY, FAILED, PASSED, QUALITY, REGRESSION, SECURITY, VERIFICATION, LLMCodePatchGate


class UnknownGateEvaluationError(KeyError):
    """Raised when gates()/blocking()/passed() is called before evaluate() for an execution_id."""


def _status(findings: list) -> str:
    return FAILED if any(finding["blocking"] for finding in findings) else PASSED


def _finding(category: str, message: str, blocking: bool) -> dict:
    return {"category": category, "message": message, "blocking": blocking}


class LLMCodePatchGateService:
    """Combines Commits #6-#10 into the five explicit release gates -- VERIFICATION,
    REGRESSION, SECURITY, COMPATIBILITY, QUALITY -- an applied Commit #5
    execution must clear before it may be accepted.

    Reuses LLMCodePatchVerificationService (Commit #6),
    LLMCodePatchRegressionService (Commit #7), LLMCodePatchSecurityService
    (Commit #8), LLMCodePatchCompatibilityService (Commit #9), and
    LLMCodePatchQualityService (Commit #10) purely for reads: evaluate()
    never triggers a new verification, regression analysis, or security/
    compatibility/quality review, it only summarizes whatever has already
    been recorded -- never a second, parallel release system. VERIFICATION,
    REGRESSION, and COMPATIBILITY fail closed (a blocking MISSING_* finding)
    when their prerequisite check was never run, mirroring those services'
    own "unknown" errors; SECURITY and QUALITY mirror their own services'
    read methods, which already report no findings rather than raising when
    nothing has been analyzed yet -- this service never invents new
    "was this run" bookkeeping beyond what each underlying service already
    tracks. Every gate is a pure function of already-computed state, so
    repeated evaluate() calls for an unchanged execution always agree, and
    evaluate() never mutates anything itself.
    """

    def __init__(
        self,
        verification_service: LLMCodePatchVerificationService,
        regression_service: LLMCodePatchRegressionService,
        security_service: LLMCodePatchSecurityService,
        compatibility_service: LLMCodePatchCompatibilityService,
        quality_service: LLMCodePatchQualityService,
    ):
        self._verification_service = verification_service
        self._regression_service = regression_service
        self._security_service = security_service
        self._compatibility_service = compatibility_service
        self._quality_service = quality_service
        self._gates_by_execution = {}
        self._gate_counter = 0

    def _make_gate(self, execution_id: str, gate_type: str, findings: list) -> LLMCodePatchGate:
        self._gate_counter += 1
        return LLMCodePatchGate(
            gate_id=f"gate-{execution_id}-{gate_type}-{self._gate_counter}",
            execution_id=execution_id,
            gate_type=gate_type,
            status=_status(findings),
            findings=findings,
            evaluated_at=datetime.now(timezone.utc),
        )

    def _evaluate_verification(self, execution_id: str) -> LLMCodePatchGate:
        try:
            has_blocking = self._verification_service.blocking(execution_id)
        except UnknownPatchVerificationError:
            findings = [_finding("MISSING_VERIFICATION", f"execution {execution_id!r} has not been verified", True)]
        else:
            findings = [_finding("VERIFICATION_FAILED", "verification reported blocking findings", True)] if has_blocking else []
        return self._make_gate(execution_id, VERIFICATION, findings)

    def _evaluate_regression(self, execution_id: str) -> LLMCodePatchGate:
        try:
            regressions = self._regression_service.regressions(execution_id)
        except UnknownRegressionAnalysisError:
            findings = [
                _finding(
                    "MISSING_REGRESSION_ANALYSIS",
                    f"execution {execution_id!r} has not had regression analysis run",
                    True,
                )
            ]
        else:
            findings = [
                _finding(
                    "REGRESSION",
                    f"test {regression.test_id!r} regressed ({regression.severity})",
                    regression.severity == REGRESSION_CRITICAL,
                )
                for regression in regressions
            ]
        return self._make_gate(execution_id, REGRESSION, findings)

    def _evaluate_security(self, execution_id: str) -> LLMCodePatchGate:
        findings = [
            _finding(finding.category, finding.evidence, finding.severity == SECURITY_CRITICAL)
            for finding in self._security_service.findings(execution_id)
        ]
        return self._make_gate(execution_id, SECURITY, findings)

    def _evaluate_compatibility(self, execution_id: str) -> LLMCodePatchGate:
        try:
            compatibility_findings = self._compatibility_service.findings(execution_id)
        except UnknownCompatibilityReviewError:
            findings = [
                _finding(
                    "MISSING_COMPATIBILITY_REVIEW",
                    f"execution {execution_id!r} has not had a compatibility review",
                    True,
                )
            ]
        else:
            findings = list(compatibility_findings)
        return self._make_gate(execution_id, COMPATIBILITY, findings)

    def _evaluate_quality(self, execution_id: str) -> LLMCodePatchGate:
        findings = [
            _finding(finding.category, finding.evidence, finding.severity == QUALITY_CRITICAL)
            for finding in self._quality_service.findings(execution_id)
        ]
        return self._make_gate(execution_id, QUALITY, findings)

    def evaluate(self, execution_id: str) -> list:
        gates = [
            self._evaluate_verification(execution_id),
            self._evaluate_regression(execution_id),
            self._evaluate_security(execution_id),
            self._evaluate_compatibility(execution_id),
            self._evaluate_quality(execution_id),
        ]
        self._gates_by_execution[execution_id] = gates
        return list(gates)

    def _tracked(self, execution_id: str) -> list:
        try:
            return self._gates_by_execution[execution_id]
        except KeyError:
            raise UnknownGateEvaluationError(execution_id)

    def gates(self, execution_id: str) -> list:
        return list(self._tracked(execution_id))

    def blocking(self, execution_id: str) -> bool:
        return any(gate.status == FAILED for gate in self._tracked(execution_id))

    def passed(self, execution_id: str) -> bool:
        return not self.blocking(execution_id)
