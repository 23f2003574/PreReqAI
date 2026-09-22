from datetime import datetime, timezone

from .drift import DRIFT_NON_BLOCKING, DRIFT_NONE
from .models import (
    FRESHNESS_FRESH,
    FRESHNESS_STALE,
    FRESHNESS_UNKNOWN,
    AgentTaskRecoveryExecutionCurrentStateEvidence,
    AgentTaskRecoveryExecutionDecisionStalenessResult,
    AgentTaskRecoveryExecutionPreconditionDecision,
)


class LLMAgentTaskRecoveryExecutionDecisionFreshnessPolicy:
    """Centralizes the one rule Commit #2's own staleness service uses to
    decide fresh/stale/indeterminate -- never a second policy framework or
    arbitrary TTL rule (Rule: "Do not invent arbitrary TTL rules or
    another policy framework"): is_fresh()/explain() are pure functions of
    exactly two already-computed inputs, `decision` (Commit #7's own
    persisted record) and `current_state` (a plain
    AgentTaskRecoveryExecutionCurrentStateEvidence bundle) -- no I/O, no
    service calls, no clock reads beyond stamping the returned result's
    own `checked_at` (Rule: "Keep the policy pure/read-only").

    Prefers explicit state/version compatibility over wall-clock age
    (Rule): staleness is decided purely from current_state_version vs.
    decision.snapshot_id (an explicit identity comparison) and
    current_state.drift_category (Commit #3's own classification) --
    nothing here ever reads or compares a timestamp to "now."

    indeterminate is never treated as fresh (Rule): current_state.ambiguous
    or a current_state_version that could not be resolved at all (None)
    both force FRESHNESS_UNKNOWN outright, checked before either the
    version-match or drift-category branches even run.

    Reuses backend.agent_task_recovery_execution_precondition_snapshots'
    own FRESHNESS_FRESH/FRESHNESS_STALE/FRESHNESS_UNKNOWN vocabulary and
    AgentTaskRecoveryExecutionDecisionStalenessResult shape verbatim
    (Rule: "Reuse existing version/freshness policies where present") --
    "indeterminate" (this commit's own wording) and Commit #2's own
    "unknown" name exactly the same status; introducing a second,
    same-meaning constant would only fragment the vocabulary, so none was
    added.
    """

    def is_fresh(
        self,
        decision: AgentTaskRecoveryExecutionPreconditionDecision,
        current_state: AgentTaskRecoveryExecutionCurrentStateEvidence,
    ) -> bool:
        """Whether decision is still fresh against current_state -- the
        same check as explain(), reduced to a bare bool."""
        return self.explain(decision, current_state).status == FRESHNESS_FRESH

    def explain(
        self,
        decision: AgentTaskRecoveryExecutionPreconditionDecision,
        current_state: AgentTaskRecoveryExecutionCurrentStateEvidence,
    ) -> AgentTaskRecoveryExecutionDecisionStalenessResult:
        """decision's complete freshness verdict against current_state."""
        decision_state_version = decision.snapshot_id
        current_state_version = current_state.current_state_version

        if current_state.ambiguous:
            status, reason = FRESHNESS_UNKNOWN, (
                "required freshness evidence is no longer available to compare against the current state"
            )
        elif current_state_version is None:
            status, reason = FRESHNESS_UNKNOWN, "no current state version could be resolved to compare against"
        elif current_state_version != decision_state_version:
            status, reason = FRESHNESS_STALE, (
                f"a newer snapshot ({current_state_version!r}) has been captured for this authorization since "
                f"this decision was made"
            )
        elif current_state.drift_category not in (DRIFT_NONE, DRIFT_NON_BLOCKING):
            status, reason = FRESHNESS_STALE, (
                f"recovery state has drifted since the decision was made: {current_state.drift_category!r}"
            )
        else:
            status, reason = FRESHNESS_FRESH, "no version or state changes detected since the decision was made"

        return AgentTaskRecoveryExecutionDecisionStalenessResult(
            task_id=decision.task_id, decision_id=decision.decision_id, status=status, reason=reason,
            decision_timestamp=decision.created_at, current_state_version=current_state_version,
            decision_state_version=decision_state_version, checked_at=self._now(),
        )

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)
