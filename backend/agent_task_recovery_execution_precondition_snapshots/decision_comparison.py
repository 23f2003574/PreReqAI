from datetime import datetime, timezone

from .decision_store import LLMAgentTaskRecoveryExecutionPreconditionDecisionStore
from .models import (
    EXECUTION_DECISION_ALLOW,
    AgentTaskRecoveryExecutionPreconditionDecisionComparison,
    AgentTaskRecoveryExecutionPreconditionFieldChange,
)


class InvalidAgentTaskRecoveryExecutionPreconditionDecisionComparisonError(ValueError):
    """Raised when compare() is given invalid arguments, decision_id/
    other_decision_id names no decision recorded for task_id, or
    other_decision_id was omitted and no previous decision exists to
    compare against."""


class LLMAgentTaskRecoveryExecutionPreconditionDecisionComparisonService:
    """Compares two Commit #7-persisted AgentTaskRecoveryExecutionPreconditionDecision
    records for the same task -- never a second diff engine (Rule: "Do not
    invent infrastructure or duplicate snapshot/validation logic"):
    compare() only ever reads through Commit #7's own store (get()/
    history()) and computes a plain field-by-field comparison of two
    already-persisted results -- it never calls validate()/classify()/
    reconcile()/decide() itself.

    other_decision_id defaults to the task's own chronologically PREVIOUS
    decision (Commit #7's own history(), the entry immediately before
    decision_id) when omitted -- the most directly useful "what changed
    since last time" reading of "the task's previous/latest applicable
    decision." Raises when decision_id is itself the first decision ever
    recorded (nothing to compare against) rather than silently comparing
    it to nothing.

    Deterministic regardless of argument order (Rule: "Preserve
    deterministic output ordering"): decision_transition/changed_fields/
    added-removed-* are always computed FROM the chronologically earlier
    of the two decisions TO the later one (by created_at), never by which
    parameter position the caller passed each id in.

    Read-only (Rule): compare() never writes to the decision store, and
    never calls any other precondition service's own write path -- it
    only ever reads two already-persisted records and diffs them.
    """

    def __init__(self, store: LLMAgentTaskRecoveryExecutionPreconditionDecisionStore = None):
        """
        Args:
            store: Defaults to a fresh
                LLMAgentTaskRecoveryExecutionPreconditionDecisionStore;
                pass the real instance holding the decisions decide()
                actually persisted.
        """
        self._store = store if store is not None else LLMAgentTaskRecoveryExecutionPreconditionDecisionStore()

    def compare(
        self, task_id: str, decision_id: str, other_decision_id: str = None
    ) -> AgentTaskRecoveryExecutionPreconditionDecisionComparison:
        """Compare task_id's exact decision_id against other_decision_id
        (or, when omitted, task_id's own chronologically previous
        decision).

        Raises:
            InvalidAgentTaskRecoveryExecutionPreconditionDecisionComparisonError:
                If task_id/decision_id is not a non-empty string, either
                decision_id names no decision recorded for task_id, or
                other_decision_id was omitted and decision_id is the
                first decision ever recorded for task_id
        """
        self._require_text(task_id, "task_id")
        self._require_text(decision_id, "decision_id")

        decision = self._store.get(decision_id)
        if decision is None or decision.task_id != task_id:
            raise InvalidAgentTaskRecoveryExecutionPreconditionDecisionComparisonError(
                f"no decision {decision_id!r} is recorded for task_id {task_id!r}"
            )

        if other_decision_id is None:
            history = self._store.history(task_id)
            index = next((i for i, entry in enumerate(history) if entry.decision_id == decision_id), None)
            previous = history[index - 1] if index is not None and index > 0 else None
            if previous is None:
                raise InvalidAgentTaskRecoveryExecutionPreconditionDecisionComparisonError(
                    f"no previous decision exists for task_id {task_id!r} to compare {decision_id!r} against"
                )
            other = previous
            other_decision_id = other.decision_id
        else:
            self._require_text(other_decision_id, "other_decision_id")
            other = self._store.get(other_decision_id)
            if other is None or other.task_id != task_id:
                raise InvalidAgentTaskRecoveryExecutionPreconditionDecisionComparisonError(
                    f"no decision {other_decision_id!r} is recorded for task_id {task_id!r}"
                )

        if other.created_at < decision.created_at:
            earlier, later = other, decision
        else:
            earlier, later = decision, other

        added_blocking = tuple(sorted(set(later.blocking_conditions) - set(earlier.blocking_conditions)))
        removed_blocking = tuple(sorted(set(earlier.blocking_conditions) - set(later.blocking_conditions)))
        added_warnings = tuple(sorted(set(later.warnings) - set(earlier.warnings)))
        removed_warnings = tuple(sorted(set(earlier.warnings) - set(later.warnings)))

        earlier_drift_category = earlier.drift_classification.category if earlier.drift_classification else None
        later_drift_category = later.drift_classification.category if later.drift_classification else None
        earlier_reconciliation_state = (
            earlier.approval_reconciliation.state if earlier.approval_reconciliation else None
        )
        later_reconciliation_state = later.approval_reconciliation.state if later.approval_reconciliation else None

        changes = []
        self._track(changes, "decision", earlier.decision, later.decision)
        self._track(changes, "snapshot_id", earlier.snapshot_id, later.snapshot_id)
        self._track(changes, "authorization_id", earlier.authorization_id, later.authorization_id)
        self._track(changes, "drift_classification_category", earlier_drift_category, later_drift_category)
        self._track(changes, "approval_reconciliation_state", earlier_reconciliation_state, later_reconciliation_state)
        if added_blocking or removed_blocking:
            self._track(changes, "blocking_conditions", earlier.blocking_conditions, later.blocking_conditions)
        if added_warnings or removed_warnings:
            self._track(changes, "warnings", earlier.warnings, later.warnings)
        changes.sort(key=lambda change: change.field)

        return AgentTaskRecoveryExecutionPreconditionDecisionComparison(
            task_id=task_id,
            decision_id=decision_id,
            other_decision_id=other_decision_id,
            earlier_decision_id=earlier.decision_id,
            later_decision_id=later.decision_id,
            decision_transition=f"{earlier.decision} -> {later.decision}",
            eligibility_changed=(earlier.decision == EXECUTION_DECISION_ALLOW)
            != (later.decision == EXECUTION_DECISION_ALLOW),
            snapshot_changed=earlier.snapshot_id != later.snapshot_id,
            authorization_changed=earlier.authorization_id != later.authorization_id,
            drift_classification_changed=earlier_drift_category != later_drift_category,
            approval_reconciliation_changed=earlier_reconciliation_state != later_reconciliation_state,
            added_blocking_conditions=added_blocking,
            removed_blocking_conditions=removed_blocking,
            added_warnings=added_warnings,
            removed_warnings=removed_warnings,
            changed_fields=tuple(changes),
            changed=bool(changes),
            compared_at=self._now(),
        )

    @staticmethod
    def _track(changes: list, field: str, previous_value, current_value) -> None:
        if previous_value != current_value:
            changes.append(
                AgentTaskRecoveryExecutionPreconditionFieldChange(
                    field=field, previous_value=previous_value, current_value=current_value
                )
            )

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryExecutionPreconditionDecisionComparisonError(
                f"{field_name} is required and must be a non-empty string"
            )
