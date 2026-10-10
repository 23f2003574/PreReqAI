from datetime import datetime, timezone

from .decision_comparison import LLMAgentTaskRecoveryExecutionPreconditionDecisionComparisonService
from .decision_store import LLMAgentTaskRecoveryExecutionPreconditionDecisionStore
from .models import (
    EXECUTION_DECISION_ALLOW,
    EXECUTION_DECISION_BLOCK,
    EXECUTION_DECISION_REVIEW,
    AgentTaskRecoveryExecutionPreconditionDecisionTransition,
)

_SEVERITY = {EXECUTION_DECISION_ALLOW: 0, EXECUTION_DECISION_REVIEW: 1, EXECUTION_DECISION_BLOCK: 2}


class InvalidAgentTaskRecoveryExecutionPreconditionDecisionTransitionError(ValueError):
    """Raised when analyze() is given invalid arguments, decision_id/
    previous_decision_id names no decision recorded for task_id, no
    decision has ever been recorded for task_id at all (when decision_id
    was omitted), or no previous decision exists to compare against (when
    previous_decision_id was omitted)."""


class LLMAgentTaskRecoveryExecutionPreconditionDecisionTransitionService:
    """Turns Commit #8's own decision comparison into a structured
    explanation of how execution eligibility moved -- never a second
    comparison engine (Rule: "Do not duplicate comparison logic or invent
    infrastructure"): analyze() calls Commit #8's own compare() exactly
    once and derives transition_type/requires_attention purely from that
    comparison's own already-computed fields; it never reruns validate()/
    classify()/reconcile()/decide() itself.

    decision_id defaults to task_id's own latest persisted decision
    (Commit #7's own store.latest()) when omitted; previous_decision_id is
    passed straight through to Commit #8's own compare() (which itself
    resolves an omitted one to the chronologically previous decision).

    requires_attention is true exactly when severity worsened (allow <
    review < block) or a genuinely new blocking condition appeared even
    without the coarse category moving -- never true for an improving or
    unchanged transition (Rule: "true for transitions that introduce a
    review/block condition or otherwise materially alter execution
    eligibility").

    Read-only (Rule): analyze() only ever reads through Commit #7's store
    and Commit #8's compare() -- it never mutates task, authorization,
    approval, or decision state.

    Deterministic (Rule): both Commit #7's store and Commit #8's compare()
    are already deterministic over fixed input, so calling analyze() twice
    in a row with nothing else changed always returns an identical result.
    """

    def __init__(
        self,
        store: LLMAgentTaskRecoveryExecutionPreconditionDecisionStore = None,
        comparison_service: LLMAgentTaskRecoveryExecutionPreconditionDecisionComparisonService = None,
    ):
        """
        Args:
            store: Defaults to a fresh
                LLMAgentTaskRecoveryExecutionPreconditionDecisionStore;
                pass the real instance holding the decisions decide()
                actually persisted.
            comparison_service: Defaults to a fresh
                LLMAgentTaskRecoveryExecutionPreconditionDecisionComparisonService;
                pass the real instance wired to the same store.
        """
        self._store = store if store is not None else LLMAgentTaskRecoveryExecutionPreconditionDecisionStore()
        self._comparison_service = (
            comparison_service
            if comparison_service is not None
            else LLMAgentTaskRecoveryExecutionPreconditionDecisionComparisonService(store=self._store)
        )

    def analyze(
        self, task_id: str, decision_id: str = None, previous_decision_id: str = None
    ) -> AgentTaskRecoveryExecutionPreconditionDecisionTransition:
        """Analyze how execution eligibility moved from
        previous_decision_id (or task_id's chronologically previous
        decision) to decision_id (or task_id's own latest decision).

        Raises:
            InvalidAgentTaskRecoveryExecutionPreconditionDecisionTransitionError:
                If task_id is not a non-empty string, decision_id was
                omitted and no decision has ever been recorded for
                task_id, or Commit #8's own compare() itself raises
                (unknown decision_id/previous_decision_id, or no previous
                decision exists)
        """
        self._require_text(task_id, "task_id")

        if decision_id is None:
            latest = self._store.latest(task_id)
            if latest is None:
                raise InvalidAgentTaskRecoveryExecutionPreconditionDecisionTransitionError(
                    f"no decision has ever been recorded for task_id {task_id!r}"
                )
            decision_id = latest.decision_id

        try:
            comparison = self._comparison_service.compare(task_id, decision_id, previous_decision_id)
        except ValueError as error:
            raise InvalidAgentTaskRecoveryExecutionPreconditionDecisionTransitionError(str(error)) from error

        from_decision, to_decision = comparison.decision_transition.split(" -> ")
        transition_type = f"{from_decision}_to_{to_decision}"

        worsened = _SEVERITY[to_decision] > _SEVERITY[from_decision]
        requires_attention = worsened or bool(comparison.added_blocking_conditions)

        return AgentTaskRecoveryExecutionPreconditionDecisionTransition(
            task_id=task_id,
            from_decision_id=comparison.earlier_decision_id,
            to_decision_id=comparison.later_decision_id,
            from_decision=from_decision,
            to_decision=to_decision,
            transition_type=transition_type,
            eligibility_changed=comparison.eligibility_changed,
            blocking_conditions_added=comparison.added_blocking_conditions,
            blocking_conditions_removed=comparison.removed_blocking_conditions,
            warnings_added=comparison.added_warnings,
            warnings_removed=comparison.removed_warnings,
            material_changes=comparison.changed_fields,
            requires_attention=requires_attention,
            analyzed_at=self._now(),
        )

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryExecutionPreconditionDecisionTransitionError(
                f"{field_name} is required and must be a non-empty string"
            )
