from dataclasses import dataclass, field
from datetime import datetime, timezone

from .decision_lifecycle_configuration_validation import (
    LLMAgentTaskRecoveryExecutionDecisionLifecycleConfigurationValidator,
)
from .decision_lifecycle_dependency_diagnostics import (
    LLMAgentTaskRecoveryExecutionDecisionLifecycleDependencyDiagnostics,
)
from .models import (
    HEALTH_BLOCKED,
    HEALTH_DEGRADED,
    HEALTH_HEALTHY,
    HEALTH_RESULT_SCHEMA_VERSION,
    HEALTH_UNAVAILABLE,
    LIFECYCLE_VERIFICATION_VALID,
    RESOLUTION_RESOLVED,
    SUPERSESSION_VALID,
)

CHECK_TASK_EXISTENCE = "task_existence"
CHECK_DECISION_STORE_AVAILABILITY = "decision_store_availability"
CHECK_AUTHORITATIVE_DECISION_RESOLUTION = "authoritative_decision_resolution"
CHECK_SUPERSESSION_CHAIN_VALIDITY = "supersession_chain_validity"
CHECK_IMPACT_STALENESS_SUBSYSTEM_AVAILABILITY = "impact_staleness_subsystem_availability"
CHECK_LIFECYCLE_RESULT_ACCESSIBILITY = "lifecycle_result_accessibility"
CHECK_UNRESOLVED_BLOCKERS = "unresolved_blockers"
CHECK_LIFECYCLE_VERIFICATION = "lifecycle_verification"


class InvalidAgentTaskRecoveryExecutionDecisionLifecycleHealthError(ValueError):
    """Raised when check() is given an invalid task_id."""


@dataclass(frozen=True)
class AgentTaskRecoveryExecutionDecisionLifecycleHealthCheck:
    """One named, pass/fail probe inside a health check() call. detail
    is a short, human-readable reference (a status/count/reason), never
    a copy of decision/snapshot content."""

    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class AgentTaskRecoveryExecutionDecisionLifecycleHealthResult:
    """LLMAgentTaskRecoveryExecutionDecisionLifecycleHealthService.check()'s
    consolidated diagnostic outcome."""

    task_id: str
    status: str
    checks: tuple
    issues: tuple
    authoritative_decision_id: object
    latest_lifecycle_result_id: object
    dependency_diagnostics: tuple
    configuration_validation: object = None
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    schema_version: int = HEALTH_RESULT_SCHEMA_VERSION

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "status": self.status,
            "checks": [dict(name=c.name, passed=c.passed, detail=c.detail) for c in self.checks],
            "issues": list(self.issues),
            "authoritative_decision_id": self.authoritative_decision_id,
            "latest_lifecycle_result_id": self.latest_lifecycle_result_id,
            "dependency_diagnostics": [
                dict(dependency=d.dependency, status=d.status, failure_reason=d.failure_reason,
                     last_verified_state=d.last_verified_state, blocking=d.blocking)
                for d in self.dependency_diagnostics
            ],
            "configuration_validation": (
                self.configuration_validation.to_dict() if self.configuration_validation is not None else None
            ),
            "checked_at": self.checked_at.isoformat(),
            "schema_version": self.schema_version,
        }


class LLMAgentTaskRecoveryExecutionDecisionLifecycleHealthService:
    """Read-only diagnostic over the same existing decision, supersession,
    impact/staleness, and lifecycle-result/verification services the
    facade (decision_lifecycle_facade.py) composes -- never the lifecycle
    or reconciliation services themselves, since both of those can run
    remediation or persist a new result. check() calls only read
    methods (resolve(), validate(), analyze(), check(), latest(),
    verify()) on its collaborators and never calls run()/reconcile()/
    record() anywhere -- no new lifecycle path, no mutation, ever.

    Distinguishes an infrastructure problem from a legitimate task-level
    one: an unexpected exception from any composed service (the store is
    down, a dependency is misconfigured) makes the result UNAVAILABLE
    and stops further checks that depend on it (fail closed); a
    dependency that answers cleanly but reports a real problem with this
    task (lineage rejected/conflicted, invalid supersession chain,
    artifacts still blocking) makes it BLOCKED instead -- the
    distinction the "healthy state" and "dependency failure" test cases
    exist to keep separate from the "task blocker" case.

    A task with no persisted lifecycle result yet (nothing to verify) or
    whose persisted result no longer verifies cleanly is DEGRADED, not
    BLOCKED: nothing is currently stopping the task, but the recorded
    outcome is incomplete or stale and evaluate() should be run again to
    refresh it.

    Deterministic: given the same underlying state, repeated check()
    calls always return the same status/checks/issues (only checked_at
    is fresh per call, the same "same signals, same status" discipline
    backend.session.ExecutionRuntimeHealthService's own check()
    documents for its own health snapshot).
    """

    def __init__(
        self,
        decision_store,
        resolution_service,
        supersession_validation_service,
        impact_service,
        staleness_service,
        lifecycle_result_service,
        lifecycle_verification_service,
        dependency_diagnostics_service: LLMAgentTaskRecoveryExecutionDecisionLifecycleDependencyDiagnostics = None,
        configuration_validator: LLMAgentTaskRecoveryExecutionDecisionLifecycleConfigurationValidator = None,
    ):
        """All seven are the existing, read-only-safe services from this
        package (decision_store.py, decision_supersession_resolution.py,
        decision_supersession_validation.py, decision_change_impact.py,
        decision_impact_staleness.py, decision_impact_invalidation_
        lifecycle_result.py, decision_impact_invalidation_lifecycle_
        verification.py). dependency_diagnostics_service is #7's
        LLMAgentTaskRecoveryExecutionDecisionLifecycleDependencyDiagnostics;
        when not given, one is built from the same seven collaborators
        above (the same "default when none given" convention this
        package's other services already use). configuration_validator
        is #12's LLMAgentTaskRecoveryExecutionDecisionLifecycleConfigurationValidator;
        when not given, one is built from these same seven -- a caller
        with the full nine-collaborator wiring (lifecycle_service and
        reconciliation_service included, e.g. backend/cli.py's
        build_recovery_decision_health_service()) should pass its own
        for a complete validation."""
        self._decision_store = decision_store
        self._resolution = resolution_service
        self._supersession_validation = supersession_validation_service
        self._impact = impact_service
        self._staleness = staleness_service
        self._results = lifecycle_result_service
        self._verification = lifecycle_verification_service
        self._dependency_diagnostics = dependency_diagnostics_service or LLMAgentTaskRecoveryExecutionDecisionLifecycleDependencyDiagnostics(
            decision_store=decision_store,
            resolution_service=resolution_service,
            supersession_validation_service=supersession_validation_service,
            impact_service=impact_service,
            staleness_service=staleness_service,
            lifecycle_result_service=lifecycle_result_service,
            lifecycle_verification_service=lifecycle_verification_service,
        )
        self._configuration_validator = configuration_validator or LLMAgentTaskRecoveryExecutionDecisionLifecycleConfigurationValidator(
            decision_store=decision_store,
            resolution_service=resolution_service,
            supersession_validation_service=supersession_validation_service,
            impact_service=impact_service,
            staleness_service=staleness_service,
            lifecycle_result_service=lifecycle_result_service,
            lifecycle_verification_service=lifecycle_verification_service,
        )

    def check(self, task_id: str) -> AgentTaskRecoveryExecutionDecisionLifecycleHealthResult:
        """Diagnose task_id's recovery execution decision lifecycle
        without executing remediation/recovery or mutating any state.

        Raises:
            InvalidAgentTaskRecoveryExecutionDecisionLifecycleHealthError:
                If task_id is not a non-empty string
        """
        if not task_id or not isinstance(task_id, str):
            raise InvalidAgentTaskRecoveryExecutionDecisionLifecycleHealthError(
                "task_id is required and must be a non-empty string"
            )

        checks, issues = [], []
        unavailable = False

        history, ok, detail = self._safe(lambda: self._decision_store.history(task_id))
        checks.append(AgentTaskRecoveryExecutionDecisionLifecycleHealthCheck(
            CHECK_DECISION_STORE_AVAILABILITY, ok, detail,
        ))
        if not ok:
            unavailable = True
            issues.append(f"decision store unavailable: {detail}")
            history = ()

        task_exists = bool(history)
        checks.append(AgentTaskRecoveryExecutionDecisionLifecycleHealthCheck(
            CHECK_TASK_EXISTENCE, task_exists,
            "decisions recorded for task_id" if task_exists else "no decisions recorded for task_id",
        ))
        if not task_exists and ok:
            issues.append("no decisions recorded for task_id")

        authoritative_decision_id = None
        chain = ()
        resolved = False
        if not unavailable:
            resolution, ok, detail = self._safe(lambda: self._resolution.resolve(task_id))
            if not ok:
                unavailable = True
                issues.append(f"decision resolution unavailable: {detail}")
                checks.append(AgentTaskRecoveryExecutionDecisionLifecycleHealthCheck(
                    CHECK_AUTHORITATIVE_DECISION_RESOLUTION, False, detail,
                ))
            else:
                resolved = resolution.resolution_state == RESOLUTION_RESOLVED
                authoritative_decision_id = resolution.terminal_decision_id if resolved else None
                chain = tuple(resolution.chain)
                checks.append(AgentTaskRecoveryExecutionDecisionLifecycleHealthCheck(
                    CHECK_AUTHORITATIVE_DECISION_RESOLUTION, resolved,
                    f"resolution_state={resolution.resolution_state}",
                ))
                if not resolved:
                    issues.append(f"authoritative decision not resolved ({resolution.resolution_state})")

        lineage_valid = False
        if not unavailable:
            supersession, ok, detail = self._safe(lambda: self._supersession_validation.validate(task_id))
            if not ok:
                unavailable = True
                issues.append(f"supersession validation unavailable: {detail}")
                checks.append(AgentTaskRecoveryExecutionDecisionLifecycleHealthCheck(
                    CHECK_SUPERSESSION_CHAIN_VALIDITY, False, detail,
                ))
            else:
                lineage_valid = supersession.status == SUPERSESSION_VALID
                checks.append(AgentTaskRecoveryExecutionDecisionLifecycleHealthCheck(
                    CHECK_SUPERSESSION_CHAIN_VALIDITY, lineage_valid, f"status={supersession.status}",
                ))
                if not lineage_valid:
                    issues.append(f"supersession chain invalid ({supersession.status})")

        if not unavailable:
            if resolved and len(chain) >= 2:
                _, ok, detail = self._safe(
                    lambda: self._staleness.check(task_id, self._impact.analyze(task_id, chain[-2], chain[-1]))
                )
                if not ok:
                    unavailable = True
                    issues.append(f"impact/staleness subsystem unavailable: {detail}")
                checks.append(AgentTaskRecoveryExecutionDecisionLifecycleHealthCheck(
                    CHECK_IMPACT_STALENESS_SUBSYSTEM_AVAILABILITY, ok, detail,
                ))
            else:
                checks.append(AgentTaskRecoveryExecutionDecisionLifecycleHealthCheck(
                    CHECK_IMPACT_STALENESS_SUBSYSTEM_AVAILABILITY, True, "not applicable: no prior decision to compare",
                ))

        latest_lifecycle_result_id = None
        blocking_free = True
        has_persisted_result = False
        if not unavailable:
            latest, ok, detail = self._safe(lambda: self._results.latest(task_id))
            checks.append(AgentTaskRecoveryExecutionDecisionLifecycleHealthCheck(
                CHECK_LIFECYCLE_RESULT_ACCESSIBILITY, ok, detail,
            ))
            if not ok:
                unavailable = True
                issues.append(f"lifecycle result store unavailable: {detail}")
            elif latest is not None:
                has_persisted_result = True
                latest_lifecycle_result_id = latest.result_id
                blocking_free = not latest.blocking_artifacts
                checks.append(AgentTaskRecoveryExecutionDecisionLifecycleHealthCheck(
                    CHECK_UNRESOLVED_BLOCKERS, blocking_free,
                    "none" if blocking_free else f"{len(latest.blocking_artifacts)} blocking artifact(s)",
                ))
                if not blocking_free:
                    issues.append("unresolved blockers exist on the latest persisted lifecycle result")
            else:
                checks.append(AgentTaskRecoveryExecutionDecisionLifecycleHealthCheck(
                    CHECK_UNRESOLVED_BLOCKERS, True, "no persisted lifecycle result to check",
                ))
                issues.append("no persisted lifecycle result found for task_id")

        verified = False
        if not unavailable:
            if has_persisted_result:
                verification, ok, detail = self._safe(
                    lambda: self._verification.verify(task_id, latest_lifecycle_result_id)
                )
                if not ok:
                    unavailable = True
                    issues.append(f"lifecycle verification unavailable: {detail}")
                    checks.append(AgentTaskRecoveryExecutionDecisionLifecycleHealthCheck(
                        CHECK_LIFECYCLE_VERIFICATION, False, detail,
                    ))
                else:
                    verified = verification.status == LIFECYCLE_VERIFICATION_VALID
                    checks.append(AgentTaskRecoveryExecutionDecisionLifecycleHealthCheck(
                        CHECK_LIFECYCLE_VERIFICATION, verified, f"status={verification.status}",
                    ))
                    if not verified:
                        issues.append(f"latest persisted lifecycle result no longer verifies ({verification.status})")
            else:
                checks.append(AgentTaskRecoveryExecutionDecisionLifecycleHealthCheck(
                    CHECK_LIFECYCLE_VERIFICATION, True, "no persisted lifecycle result to verify",
                ))

        blocked = (not unavailable) and (
            (not task_exists) or (not resolved) or (not lineage_valid) or (not blocking_free)
        )
        degraded = (not unavailable) and (not blocked) and (not has_persisted_result or not verified)

        if unavailable:
            status = HEALTH_UNAVAILABLE
        elif blocked:
            status = HEALTH_BLOCKED
        elif degraded:
            status = HEALTH_DEGRADED
        else:
            status = HEALTH_HEALTHY

        return AgentTaskRecoveryExecutionDecisionLifecycleHealthResult(
            task_id=task_id,
            status=status,
            checks=tuple(checks),
            issues=tuple(issues),
            authoritative_decision_id=authoritative_decision_id,
            latest_lifecycle_result_id=latest_lifecycle_result_id,
            dependency_diagnostics=self._dependency_diagnostics.diagnose(task_id),
            configuration_validation=self._configuration_validator.validate(),
        )

    @staticmethod
    def _safe(call):
        try:
            return call(), True, "ok"
        except Exception as error:
            return None, False, f"{type(error).__name__}: {error}"
