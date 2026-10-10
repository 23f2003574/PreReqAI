from dataclasses import dataclass

from .models import (
    HEALTH_BLOCKED,
    HEALTH_DEGRADED,
    HEALTH_HEALTHY,
    HEALTH_UNAVAILABLE,
    LIFECYCLE_VERIFICATION_VALID,
    RESOLUTION_RESOLVED,
    SUPERSESSION_VALID,
)

DEPENDENCY_DECISION_STORE = "decision_store"
DEPENDENCY_SUPERSESSION_RESOLVER = "supersession_resolver"
DEPENDENCY_IMPACT_ANALYZER = "impact_analyzer"
DEPENDENCY_STALENESS_DETECTOR = "staleness_detector"
DEPENDENCY_REMEDIATION_RECONCILIATION = "remediation_reconciliation"
DEPENDENCY_LIFECYCLE_RESULT_PERSISTENCE = "lifecycle_result_persistence"
DEPENDENCY_VERIFICATION = "verification"

# Fixed return order -- "Deterministic dependency ordering" -- matching
# the order the task's own dependency list names them in, independent of
# the order they happen to be probed in below.
DEPENDENCY_ORDER = (
    DEPENDENCY_DECISION_STORE,
    DEPENDENCY_SUPERSESSION_RESOLVER,
    DEPENDENCY_IMPACT_ANALYZER,
    DEPENDENCY_STALENESS_DETECTOR,
    DEPENDENCY_REMEDIATION_RECONCILIATION,
    DEPENDENCY_LIFECYCLE_RESULT_PERSISTENCE,
    DEPENDENCY_VERIFICATION,
)


class InvalidAgentTaskRecoveryExecutionDecisionLifecycleDependencyDiagnosticsError(ValueError):
    """Raised when diagnose() is given an invalid task_id."""


@dataclass(frozen=True)
class AgentTaskRecoveryExecutionDecisionLifecycleDependencyDiagnostic:
    """One dependency's own healthy/degraded/blocked/unavailable verdict.
    failure_reason and last_verified_state are short reference labels
    (a status value, a count, an exception type/message) -- never a copy
    of decision/snapshot/authorization content, so nothing secret or
    sensitive ever appears here."""

    dependency: str
    status: str
    failure_reason: object
    last_verified_state: str
    blocking: bool


class LLMAgentTaskRecoveryExecutionDecisionLifecycleDependencyDiagnostics:
    """Per-dependency breakdown behind LLMAgentTaskRecoveryExecutionDecision
    LifecycleHealthService's (#6) aggregate healthy/degraded/blocked/
    unavailable verdict -- reusing the exact same seven read-only
    collaborators #6 composes (decision_store, resolution_service,
    supersession_validation_service, impact_service, staleness_service,
    lifecycle_result_service, lifecycle_verification_service) and #6's
    own status vocabulary (HEALTH_*), never a second one.

    Read-only and never executes remediation/recovery, the same
    guarantee #6 makes: diagnose() only ever calls resolve(), validate(),
    analyze(), check(), latest(), and verify() -- never run()/
    reconcile()/record() -- so "remediation_reconciliation"'s own
    diagnostic is derived entirely from the latest already-persisted
    lifecycle result's own status/blocking_artifacts/errors (what that
    dependency last actually produced), never by invoking the lifecycle
    or reconciliation service, which this class does not even take as a
    collaborator.

    A dependency reachable but reporting a real, current problem with
    this task (no decisions recorded, lineage rejected/conflicted,
    invalid supersession chain, artifacts still blocking) is BLOCKED
    (blocking=True); one that answers but with a gap or a result that no
    longer verifies is DEGRADED (blocking=False); an exception from the
    dependency itself is UNAVAILABLE (blocking=True, fail closed) --
    the same task-level-blocker-vs-infrastructure-failure split #6
    already establishes, just attributed to the one dependency
    responsible instead of rolled into one aggregate verdict.
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
    ):
        self._decision_store = decision_store
        self._resolution = resolution_service
        self._supersession_validation = supersession_validation_service
        self._impact = impact_service
        self._staleness = staleness_service
        self._results = lifecycle_result_service
        self._verification = lifecycle_verification_service

    def diagnose(self, task_id: str) -> tuple:
        """Diagnose each tracked dependency for task_id, without
        executing remediation/recovery or mutating any state.

        Raises:
            InvalidAgentTaskRecoveryExecutionDecisionLifecycleDependencyDiagnosticsError:
                If task_id is not a non-empty string
        """
        if not task_id or not isinstance(task_id, str):
            raise InvalidAgentTaskRecoveryExecutionDecisionLifecycleDependencyDiagnosticsError(
                "task_id is required and must be a non-empty string"
            )

        entries = {}

        history, ok, detail = self._safe(lambda: self._decision_store.history(task_id))
        if not ok:
            entries[DEPENDENCY_DECISION_STORE] = self._entry(DEPENDENCY_DECISION_STORE, HEALTH_UNAVAILABLE, detail, detail, True)
        elif not history:
            entries[DEPENDENCY_DECISION_STORE] = self._entry(
                DEPENDENCY_DECISION_STORE, HEALTH_BLOCKED, "no decisions recorded for task_id", "empty", True,
            )
        else:
            entries[DEPENDENCY_DECISION_STORE] = self._entry(
                DEPENDENCY_DECISION_STORE, HEALTH_HEALTHY, None, f"{len(history)} decision(s) recorded", False,
            )

        resolution, rok, rdetail = self._safe(lambda: self._resolution.resolve(task_id))
        resolved, chain = False, ()
        if not rok:
            entries[DEPENDENCY_SUPERSESSION_RESOLVER] = self._entry(
                DEPENDENCY_SUPERSESSION_RESOLVER, HEALTH_UNAVAILABLE, rdetail, rdetail, True,
            )
        else:
            resolved = resolution.resolution_state == RESOLUTION_RESOLVED
            chain = tuple(resolution.chain)
            if not resolved:
                entries[DEPENDENCY_SUPERSESSION_RESOLVER] = self._entry(
                    DEPENDENCY_SUPERSESSION_RESOLVER, HEALTH_BLOCKED,
                    f"authoritative decision not resolved ({resolution.resolution_state})",
                    f"resolution_state={resolution.resolution_state}", True,
                )
            else:
                supersession, sok, sdetail = self._safe(lambda: self._supersession_validation.validate(task_id))
                if not sok:
                    entries[DEPENDENCY_SUPERSESSION_RESOLVER] = self._entry(
                        DEPENDENCY_SUPERSESSION_RESOLVER, HEALTH_UNAVAILABLE, sdetail, sdetail, True,
                    )
                elif supersession.status != SUPERSESSION_VALID:
                    entries[DEPENDENCY_SUPERSESSION_RESOLVER] = self._entry(
                        DEPENDENCY_SUPERSESSION_RESOLVER, HEALTH_BLOCKED,
                        f"supersession chain invalid ({supersession.status})", f"status={supersession.status}", True,
                    )
                else:
                    entries[DEPENDENCY_SUPERSESSION_RESOLVER] = self._entry(
                        DEPENDENCY_SUPERSESSION_RESOLVER, HEALTH_HEALTHY, None,
                        f"resolution_state={resolution.resolution_state}", False,
                    )

        if resolved and len(chain) >= 2:
            impact, iok, idetail = self._safe(lambda: self._impact.analyze(task_id, chain[-2], chain[-1]))
            if not iok:
                entries[DEPENDENCY_IMPACT_ANALYZER] = self._entry(
                    DEPENDENCY_IMPACT_ANALYZER, HEALTH_UNAVAILABLE, idetail, idetail, True,
                )
                entries[DEPENDENCY_STALENESS_DETECTOR] = self._entry(
                    DEPENDENCY_STALENESS_DETECTOR, HEALTH_UNAVAILABLE, "impact analyzer unavailable", "not checked", True,
                )
            else:
                entries[DEPENDENCY_IMPACT_ANALYZER] = self._entry(DEPENDENCY_IMPACT_ANALYZER, HEALTH_HEALTHY, None, "analyzed", False)
                staleness, sok2, sdetail2 = self._safe(lambda: self._staleness.check(task_id, impact))
                if not sok2:
                    entries[DEPENDENCY_STALENESS_DETECTOR] = self._entry(
                        DEPENDENCY_STALENESS_DETECTOR, HEALTH_UNAVAILABLE, sdetail2, sdetail2, True,
                    )
                else:
                    stale_count = sum(1 for artifact in staleness.artifacts if artifact.status == "stale")
                    entries[DEPENDENCY_STALENESS_DETECTOR] = self._entry(
                        DEPENDENCY_STALENESS_DETECTOR, HEALTH_HEALTHY, None, f"{stale_count} stale artifact(s)", False,
                    )
        else:
            for name in (DEPENDENCY_IMPACT_ANALYZER, DEPENDENCY_STALENESS_DETECTOR):
                entries[name] = self._entry(name, HEALTH_HEALTHY, None, "not applicable: no prior decision to compare", False)

        latest, lok, ldetail = self._safe(lambda: self._results.latest(task_id))
        if not lok:
            entries[DEPENDENCY_LIFECYCLE_RESULT_PERSISTENCE] = self._entry(
                DEPENDENCY_LIFECYCLE_RESULT_PERSISTENCE, HEALTH_UNAVAILABLE, ldetail, ldetail, True,
            )
            entries[DEPENDENCY_REMEDIATION_RECONCILIATION] = self._entry(
                DEPENDENCY_REMEDIATION_RECONCILIATION, HEALTH_UNAVAILABLE,
                "lifecycle result persistence unavailable", "not checked", True,
            )
            entries[DEPENDENCY_VERIFICATION] = self._entry(
                DEPENDENCY_VERIFICATION, HEALTH_UNAVAILABLE, "lifecycle result persistence unavailable", "not checked", True,
            )
        else:
            entries[DEPENDENCY_LIFECYCLE_RESULT_PERSISTENCE] = self._entry(
                DEPENDENCY_LIFECYCLE_RESULT_PERSISTENCE, HEALTH_HEALTHY, None, "reachable", False,
            )
            if latest is None:
                entries[DEPENDENCY_REMEDIATION_RECONCILIATION] = self._entry(
                    DEPENDENCY_REMEDIATION_RECONCILIATION, HEALTH_DEGRADED,
                    "no persisted lifecycle result found for task_id", "none", False,
                )
                entries[DEPENDENCY_VERIFICATION] = self._entry(
                    DEPENDENCY_VERIFICATION, HEALTH_HEALTHY, None, "no persisted lifecycle result to verify", False,
                )
            else:
                if latest.blocking_artifacts:
                    entries[DEPENDENCY_REMEDIATION_RECONCILIATION] = self._entry(
                        DEPENDENCY_REMEDIATION_RECONCILIATION, HEALTH_BLOCKED,
                        f"{len(latest.blocking_artifacts)} blocking artifact(s)", f"status={latest.status}", True,
                    )
                elif latest.errors:
                    entries[DEPENDENCY_REMEDIATION_RECONCILIATION] = self._entry(
                        DEPENDENCY_REMEDIATION_RECONCILIATION, HEALTH_DEGRADED,
                        "; ".join(latest.errors), f"status={latest.status}", False,
                    )
                else:
                    entries[DEPENDENCY_REMEDIATION_RECONCILIATION] = self._entry(
                        DEPENDENCY_REMEDIATION_RECONCILIATION, HEALTH_HEALTHY, None, f"status={latest.status}", False,
                    )

                verification, vok, vdetail = self._safe(lambda: self._verification.verify(task_id, latest.result_id))
                if not vok:
                    entries[DEPENDENCY_VERIFICATION] = self._entry(DEPENDENCY_VERIFICATION, HEALTH_UNAVAILABLE, vdetail, vdetail, True)
                elif verification.status != LIFECYCLE_VERIFICATION_VALID:
                    entries[DEPENDENCY_VERIFICATION] = self._entry(
                        DEPENDENCY_VERIFICATION, HEALTH_DEGRADED,
                        f"latest persisted lifecycle result no longer verifies ({verification.status})",
                        f"status={verification.status}", False,
                    )
                else:
                    entries[DEPENDENCY_VERIFICATION] = self._entry(
                        DEPENDENCY_VERIFICATION, HEALTH_HEALTHY, None, f"status={verification.status}", False,
                    )

        return tuple(entries[name] for name in DEPENDENCY_ORDER)

    @staticmethod
    def _entry(dependency, status, failure_reason, last_verified_state, blocking):
        return AgentTaskRecoveryExecutionDecisionLifecycleDependencyDiagnostic(
            dependency=dependency, status=status, failure_reason=failure_reason,
            last_verified_state=last_verified_state, blocking=blocking,
        )

    @staticmethod
    def _safe(call):
        try:
            return call(), True, "ok"
        except Exception as error:
            return None, False, f"{type(error).__name__}: {error}"
