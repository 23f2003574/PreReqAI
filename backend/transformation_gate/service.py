from datetime import datetime, timezone

from backend.code_quality import ERROR as QUALITY_ERROR
from backend.code_quality import LLMCodeQualityService
from backend.code_transformation import LLMCodeTransformationService
from backend.transformation_diff import LLMTransformationDiffService
from backend.transformation_execution import LLMTransformationExecutionService
from backend.transformation_regression import CRITICAL, LLMTransformationRegressionService
from backend.transformation_regression import UnknownRegressionAnalysisError
from backend.transformation_verification import LLMTransformationVerificationService, UnknownVerificationError

from .models import FAILED, PASSED, QUALITY, REGRESSION, SECURITY, VERIFICATION, LLMTransformationGate


class UnknownGateEvaluationError(KeyError):
    """Raised when gates()/blocking()/passed() is called before evaluate() for an execution_id."""


_DANGEROUS_PATTERNS = (
    ("eval(", "eval() can execute arbitrary code"),
    ("exec(", "exec() can execute arbitrary code"),
    ("os.system(", "os.system() can execute arbitrary shell commands"),
    ("subprocess.", "subprocess usage can execute arbitrary shell commands"),
    ("pickle.loads(", "pickle.loads() can execute arbitrary code from untrusted input"),
    ("__import__(", "dynamic __import__ can load arbitrary modules"),
)


def _status(findings: list) -> str:
    return FAILED if any(finding["blocking"] for finding in findings) else PASSED


class LLMTransformationGateService:
    """Evaluates the four release gates -- VERIFICATION, REGRESSION,
    SECURITY, QUALITY -- an applied execution must clear before promotion.

    Reuses LLMTransformationVerificationService (Commit #6),
    LLMTransformationRegressionService (Commit #7), and the notebook's own
    LLMCodeQualityService findings purely for reads: evaluate() never
    triggers a new verification, regression analysis, or quality scan, it
    only summarizes whatever has already been recorded. SECURITY has no
    prior commit to reuse, so it is a static, deterministic pattern-scan of
    the execution's own already-applied source. VERIFICATION and REGRESSION
    fail closed when their prerequisite analysis was never run (release
    readiness can't be claimed for a check nobody ran); QUALITY has no such
    mandatory prerequisite in this codebase, so an unanalyzed notebook
    reports no quality findings rather than failing. Every gate is a pure
    function of already-computed state, so repeated evaluate() calls for
    an unchanged execution always agree, and evaluate() never mutates
    anything itself.
    """

    def __init__(
        self,
        execution_service: LLMTransformationExecutionService,
        diff_service: LLMTransformationDiffService,
        transformation_service: LLMCodeTransformationService,
        verification_service: LLMTransformationVerificationService,
        regression_service: LLMTransformationRegressionService,
        code_quality_service: LLMCodeQualityService,
    ):
        self._execution_service = execution_service
        self._diff_service = diff_service
        self._transformation_service = transformation_service
        self._verification_service = verification_service
        self._regression_service = regression_service
        self._code_quality_service = code_quality_service
        self._gates_by_execution = {}
        self._gate_counter = 0

    def _notebook_id_for(self, execution) -> str:
        diff = self._diff_service.get(execution.diff_id)
        plan = self._transformation_service.get(diff.plan_id)
        return plan.notebook_id

    def _make_gate(self, execution_id: str, gate_type: str, findings: list) -> LLMTransformationGate:
        self._gate_counter += 1
        return LLMTransformationGate(
            gate_id=f"gate-{execution_id}-{gate_type}-{self._gate_counter}",
            execution_id=execution_id,
            gate_type=gate_type,
            status=_status(findings),
            findings=findings,
            evaluated_at=datetime.now(timezone.utc),
        )

    def _evaluate_verification(self, execution_id: str) -> LLMTransformationGate:
        try:
            has_blocking = self._verification_service.blocking(execution_id)
        except UnknownVerificationError:
            findings = [
                {
                    "category": "MISSING_VERIFICATION",
                    "message": f"execution {execution_id!r} has not been verified",
                    "blocking": True,
                }
            ]
        else:
            findings = (
                [
                    {
                        "category": "VERIFICATION_FAILED",
                        "message": "verification reported blocking findings",
                        "blocking": True,
                    }
                ]
                if has_blocking
                else []
            )
        return self._make_gate(execution_id, VERIFICATION, findings)

    def _evaluate_regression(self, execution_id: str) -> LLMTransformationGate:
        try:
            regressions = self._regression_service.regressions(execution_id)
        except UnknownRegressionAnalysisError:
            findings = [
                {
                    "category": "MISSING_REGRESSION_ANALYSIS",
                    "message": f"execution {execution_id!r} has not had regression analysis run",
                    "blocking": True,
                }
            ]
        else:
            findings = [
                {
                    "category": "REGRESSION",
                    "message": f"test {regression.test_id!r} regressed ({regression.severity})",
                    "blocking": regression.severity == CRITICAL,
                }
                for regression in regressions
            ]
        return self._make_gate(execution_id, REGRESSION, findings)

    def _evaluate_security(self, execution) -> LLMTransformationGate:
        findings = []
        for applied in execution.applied_cells:
            source = applied["applied_source"]
            for pattern, message in _DANGEROUS_PATTERNS:
                if pattern in source:
                    findings.append(
                        {
                            "category": "SECURITY",
                            "message": f"cell {applied['cell_index']}: {message}",
                            "blocking": True,
                        }
                    )
        return self._make_gate(execution.execution_id, SECURITY, findings)

    def _evaluate_quality(self, execution, notebook_id: str) -> LLMTransformationGate:
        findings = [
            {
                "category": finding.category,
                "message": finding.message,
                "blocking": finding.severity == QUALITY_ERROR,
            }
            for finding in self._code_quality_service.findings(notebook_id)
        ]
        return self._make_gate(execution.execution_id, QUALITY, findings)

    def evaluate(self, execution_id: str) -> list:
        execution = self._execution_service.get(execution_id)
        notebook_id = self._notebook_id_for(execution)

        gates = [
            self._evaluate_verification(execution_id),
            self._evaluate_regression(execution_id),
            self._evaluate_security(execution),
            self._evaluate_quality(execution, notebook_id),
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
