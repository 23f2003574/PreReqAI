from .models import (
    ARTIFACT_FRESH,
    ARTIFACT_STALE,
    ARTIFACT_UNKNOWN,
    CHANGE_IMPACT_UNKNOWN,
    AgentTaskRecoveryExecutionDecisionImpactArtifact,
    AgentTaskRecoveryExecutionDecisionImpactStalenessResult,
)

# Snapshot-backed artifact kinds: (kind, impact area, blocking when stale)
_SNAPSHOT_KINDS = (
    ("execution_snapshot", "precondition_snapshot", True),
    ("authorization", "authorization", True),
    ("preflight", "preflight", True),
    ("recovery_plan", "recovery_plan", True),
    ("retry_budget", "retry_budget", False),
    ("readiness", "readiness", False),
)


class InvalidAgentTaskRecoveryExecutionDecisionImpactStalenessError(ValueError):
    """Raised when check() is given invalid arguments or an impact result
    for another task."""


class LLMAgentTaskRecoveryExecutionDecisionImpactStalenessService:
    """Detects downstream artifacts made stale by a change of the
    authoritative execution decision -- detection only: it reads the
    change-impact result (#1) and the artifacts already persisted with
    explicit decision/version references, and never mutates, invalidates
    or executes anything. No new dependency graph: the only links followed
    are the ones the artifacts themselves record.

      * precondition snapshot, authorization, preflight, recovery plan,
        retry/budget and readiness state -- the previous decision's own
        snapshot, stale when the impact result shows that area changed;
      * the execution/current-decision pointer (the freshness chain
        index), the latest freshness reconciliation result, and the
        latest supersession lifecycle result -- each stale when the
        decision id it records is not the current decision.

    Explicit version mismatches decide; timestamps are never used. An
    artifact whose version cannot be established (missing impact
    evidence, or a record carrying no decision reference) is UNKNOWN,
    which is blocking and never counted as fresh.
    """

    def __init__(self, chain_index_store=None, reconciliation_result_service=None, lifecycle_result_service=None):
        """Each collaborator is optional; an unconfigured one is listed in
        `unchecked` rather than guessed about."""
        self._index_store = chain_index_store
        self._reconciliation_results = reconciliation_result_service
        self._lifecycle_results = lifecycle_result_service

    def check(self, task_id: str, impact_result) -> AgentTaskRecoveryExecutionDecisionImpactStalenessResult:
        """Check task_id's downstream artifacts against impact_result.

        Raises:
            InvalidAgentTaskRecoveryExecutionDecisionImpactStalenessError:
                If task_id is not a non-empty string, or impact_result is
                missing or belongs to another task
        """
        if not task_id or not isinstance(task_id, str):
            raise InvalidAgentTaskRecoveryExecutionDecisionImpactStalenessError(
                "task_id is required and must be a non-empty string"
            )
        if impact_result is None or impact_result.task_id != task_id:
            raise InvalidAgentTaskRecoveryExecutionDecisionImpactStalenessError(
                "impact_result does not belong to the task_id given"
            )

        current = impact_result.current_decision_id
        previous = impact_result.previous_decision_id
        evidence_complete = impact_result.execution_impact != CHANGE_IMPACT_UNKNOWN and not impact_result.missing_evidence
        changed = set(impact_result.changed_areas)
        artifacts, unchecked = [], []

        def add(kind, reference, expected, status, blocking, reason):
            artifacts.append(
                AgentTaskRecoveryExecutionDecisionImpactArtifact(
                    kind=kind, reference=reference, expected=expected, status=status,
                    blocking=blocking or status == ARTIFACT_UNKNOWN, reason=reason,
                )
            )

        for kind, area, blocking in _SNAPSHOT_KINDS:
            if area in changed:
                add(kind, previous, current, ARTIFACT_STALE, blocking,
                    f"{kind} captured for decision {previous} changed under decision {current}")
            elif not evidence_complete:
                add(kind, previous, None, ARTIFACT_UNKNOWN, blocking,
                    f"{kind} version cannot be established: {'; '.join(impact_result.missing_evidence) or 'decision evidence missing'}")
            else:
                add(kind, previous, current, ARTIFACT_FRESH, False, f"{kind} is unchanged between the two decisions")

        def decision_ref(kind, reference, blocking, missing_reason):
            if reference is None:
                add(kind, None, current, ARTIFACT_UNKNOWN, blocking, missing_reason)
            elif reference != current:
                add(kind, reference, current, ARTIFACT_STALE, blocking,
                    f"{kind} references decision {reference}, not the authoritative decision {current}")
            else:
                add(kind, reference, current, ARTIFACT_FRESH, False, f"{kind} references the authoritative decision")

        if self._index_store is None:
            unchecked.append("execution_pointer")
        else:
            index = self._index_store.get(task_id)
            if index is not None:
                decision_ref("execution_pointer", index.current_decision_id, True,
                             "the execution pointer names no current decision")
        if self._reconciliation_results is None:
            unchecked.append("reconciliation_result")
        else:
            latest = self._reconciliation_results.latest(task_id)
            if latest is not None:
                decision_ref("reconciliation_result", latest.authoritative_decision_id, False,
                             f"reconciliation result {latest.result_id} records no authoritative decision")
        if self._lifecycle_results is None:
            unchecked.append("lifecycle_result")
        else:
            latest = self._lifecycle_results.latest(task_id)
            if latest is not None:
                decision_ref("lifecycle_result", latest.terminal_decision_id, False,
                             f"lifecycle result {latest.result_id} records no terminal decision")

        stale = tuple(a for a in artifacts if a.status == ARTIFACT_STALE)
        unknown = tuple(a for a in artifacts if a.status == ARTIFACT_UNKNOWN)
        status = ARTIFACT_STALE if stale else ARTIFACT_UNKNOWN if unknown else ARTIFACT_FRESH
        return AgentTaskRecoveryExecutionDecisionImpactStalenessResult(
            task_id=task_id, status=status, artifacts=tuple(artifacts), stale_artifacts=stale,
            unknown_artifacts=unknown, blocking_artifacts=tuple(a for a in artifacts if a.blocking),
            revalidation_required=bool(stale or unknown or impact_result.requires_revalidation),
            unchecked=tuple(unchecked),
        )
