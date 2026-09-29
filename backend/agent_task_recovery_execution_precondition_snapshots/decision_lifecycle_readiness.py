from dataclasses import dataclass

from .decision_lifecycle_configuration_validation import CONFIGURATION_VALID
from .decision_lifecycle_health import (
    CHECK_AUTHORITATIVE_DECISION_RESOLUTION,
    CHECK_LIFECYCLE_VERIFICATION,
    CHECK_SUPERSESSION_CHAIN_VALIDITY,
)
from .models import (
    HEALTH_BLOCKED,
    HEALTH_DEGRADED,
    HEALTH_HEALTHY,
    HEALTH_UNAVAILABLE,
)

READY = "ready"
BLOCKED = "blocked"

LINEAGE_VALID = "valid"
LINEAGE_INVALID = "invalid"
LINEAGE_NOT_APPLICABLE = "not_applicable"

READINESS_VERIFICATION_VALID = "valid"
READINESS_VERIFICATION_INVALID = "invalid"
READINESS_VERIFICATION_NOT_APPLICABLE = "not_applicable"

_HEALTH_SEVERITY = {HEALTH_HEALTHY: 0, HEALTH_DEGRADED: 1, HEALTH_BLOCKED: 2, HEALTH_UNAVAILABLE: 3}


class InvalidAgentTaskRecoveryExecutionDecisionLifecycleReadinessError(ValueError):
    """Raised when check() is given an invalid task_id."""


@dataclass(frozen=True)
class AgentTaskRecoveryExecutionDecisionLifecycleReadinessResult:
    """LLMAgentTaskRecoveryExecutionDecisionLifecycleReadinessService.check()'s
    single pass/fail deploy/readiness verdict."""

    status: str
    issues: tuple
    configuration_status: str
    dependency_status: str
    decision_lineage_status: str
    verification_status: str
    blocking_conditions: tuple

    @property
    def ready(self) -> bool:
        return self.status == READY

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "issues": list(self.issues),
            "configuration_status": self.configuration_status,
            "dependency_status": self.dependency_status,
            "decision_lineage_status": self.decision_lineage_status,
            "verification_status": self.verification_status,
            "blocking_conditions": list(self.blocking_conditions),
        }


class LLMAgentTaskRecoveryExecutionDecisionLifecycleReadinessService:
    """Composes #12's configuration validator, #6's health service
    (which itself already composes #7's dependency diagnostics), and the
    existing lifecycle_result_service into one deploy/readiness gate --
    never a new execution or recovery subsystem, and never a new
    diagnostic implementation: every check here is read straight off an
    existing diagnostic's own already-computed output.

    check(task_id=None):
      - always validates configuration and required-dependency
        availability (#12) -- the part of readiness that holds whether
        or not a task is given, since it is about whether this lifecycle
        can run at all, not about any one task's own state.
      - when task_id is given, also calls health_service.check(task_id)
        (#6, read-only) and reads the persisted lifecycle result
        (lifecycle_result_service.latest(), also read-only) for that
        task's own decision lineage, verification, and blocking-condition
        state. Never calls facade.evaluate(), lifecycle_service.run(), or
        reconciliation_service.reconcile() -- readiness only ever asks
        whether the lifecycle CAN run cleanly, never runs it.

    Deterministic: the same underlying configuration/health/persisted
    state always produces the same status/issues/*_status fields.
    """

    def __init__(self, configuration_validator, health_service, lifecycle_result_service):
        self._configuration_validator = configuration_validator
        self._health = health_service
        self._results = lifecycle_result_service

    def check(self, task_id: str = None) -> AgentTaskRecoveryExecutionDecisionLifecycleReadinessResult:
        """Raises:
            InvalidAgentTaskRecoveryExecutionDecisionLifecycleReadinessError:
                If task_id is given and is not a non-empty string
        """
        if task_id is not None and (not isinstance(task_id, str) or not task_id):
            raise InvalidAgentTaskRecoveryExecutionDecisionLifecycleReadinessError(
                "task_id must be a non-empty string when given"
            )

        issues = []

        configuration = self._configuration_validator.validate()
        configuration_status = configuration.status
        if configuration_status != CONFIGURATION_VALID:
            issues.extend(f"configuration: missing dependency {item}" for item in configuration.missing_dependencies)
            issues.extend(f"configuration: {item}" for item in configuration.issues)
            issues.extend(f"configuration: {item}" for item in configuration.unsupported_configuration)

        dependency_status = HEALTH_HEALTHY if configuration_status == CONFIGURATION_VALID else HEALTH_UNAVAILABLE
        decision_lineage_status = LINEAGE_NOT_APPLICABLE
        verification_status = READINESS_VERIFICATION_NOT_APPLICABLE
        blocking_conditions = ()

        if task_id is not None:
            health_result = self._health.check(task_id)
            dependency_status = self._worse(dependency_status, health_result.status)
            for diagnostic in health_result.dependency_diagnostics:
                if diagnostic.status != HEALTH_HEALTHY:
                    issues.append(f"dependency {diagnostic.dependency}: {diagnostic.failure_reason}")

            # Health.check() fails closed and stops probing further
            # checks once something upstream is unavailable (#6), so not
            # every named check is guaranteed present -- a missing check
            # is treated the same as a failed one (fail closed), never
            # assumed fine.
            checks_by_name = {check.name: check for check in health_result.checks}

            def _passed(name):
                check = checks_by_name.get(name)
                return check is not None and check.passed

            lineage_ok = _passed(CHECK_AUTHORITATIVE_DECISION_RESOLUTION) and _passed(CHECK_SUPERSESSION_CHAIN_VALIDITY)
            decision_lineage_status = LINEAGE_VALID if lineage_ok else LINEAGE_INVALID
            if not lineage_ok:
                issues.append("decision lineage is invalid or unresolved")

            verification_ok = _passed(CHECK_LIFECYCLE_VERIFICATION)
            verification_status = READINESS_VERIFICATION_VALID if verification_ok else READINESS_VERIFICATION_INVALID
            if not verification_ok:
                issues.append("lifecycle verification failed or is stale")

            try:
                record = self._results.latest(task_id)
            except Exception:
                record = None  # already reflected as dependency_status unavailable above; fail closed, don't crash
            if record is not None and record.blocking_artifacts:
                blocking_conditions = tuple(record.blocking_artifacts)
                issues.append(f"{len(blocking_conditions)} blocking condition(s) unresolved (may include manual_review)")

        ready = (
            configuration_status == CONFIGURATION_VALID
            and dependency_status == HEALTH_HEALTHY
            and decision_lineage_status in (LINEAGE_VALID, LINEAGE_NOT_APPLICABLE)
            and verification_status in (READINESS_VERIFICATION_VALID, READINESS_VERIFICATION_NOT_APPLICABLE)
            and blocking_conditions == ()
        )

        return AgentTaskRecoveryExecutionDecisionLifecycleReadinessResult(
            status=READY if ready else BLOCKED,
            issues=tuple(issues),
            configuration_status=configuration_status,
            dependency_status=dependency_status,
            decision_lineage_status=decision_lineage_status,
            verification_status=verification_status,
            blocking_conditions=blocking_conditions,
        )

    @staticmethod
    def _worse(a, b):
        return a if _HEALTH_SEVERITY.get(a, 0) >= _HEALTH_SEVERITY.get(b, 0) else b
