from datetime import datetime, timezone
from typing import Optional

from .decision_store import LLMAgentTaskRecoveryExecutionPreconditionDecisionStore
from .decision_transition import LLMAgentTaskRecoveryExecutionPreconditionDecisionTransitionService
from .models import (
    EXECUTION_DECISION_ALLOW,
    EXECUTION_DECISIONS,
    AgentTaskRecoveryExecutionPreconditionDecisionHistory,
    AgentTaskRecoveryExecutionPreconditionDecisionHistorySummary,
)


class InvalidAgentTaskRecoveryExecutionPreconditionDecisionHistoryError(ValueError):
    """Raised when get_history()/summarize() is given invalid arguments."""


class LLMAgentTaskRecoveryExecutionPreconditionDecisionHistoryService:
    """A dedicated read model over one task's complete Commit #7 decision
    history -- never a second persistence/comparison engine (Rule: "Do
    not invent persistence infrastructure or duplicate decision/
    comparison logic"): get_history() only ever reads through Commit #7's
    own store.history() and Commit #9's own analyze() -- it never reruns
    validate()/classify()/reconcile()/decide() itself.

    `limit` only ever trims which raw records `decisions` returns for
    display (Rule: "limit should return the most recent relevant records
    while maintaining chronological ordering"); every aggregate field
    (decision_count, counts_by_decision, transitions, eligibility_change_count,
    review_or_block_transition_count, first/latest) always reflects the
    task's COMPLETE history, never the limited slice -- a caller asking
    for the last 5 records still gets an honest total count and complete
    transition trail, not a truncated one.

    Read-only (Rule): every call here only ever reads.

    Deterministic (Rule): Commit #7's store and Commit #9's analyze() are
    already deterministic over fixed input, so calling get_history()
    twice in a row with nothing else changed always returns an identical
    result.
    """

    def __init__(
        self,
        store: LLMAgentTaskRecoveryExecutionPreconditionDecisionStore = None,
        transition_service: LLMAgentTaskRecoveryExecutionPreconditionDecisionTransitionService = None,
    ):
        """
        Args:
            store: Defaults to a fresh
                LLMAgentTaskRecoveryExecutionPreconditionDecisionStore;
                pass the real instance holding the decisions decide()
                actually persisted.
            transition_service: Defaults to a fresh
                LLMAgentTaskRecoveryExecutionPreconditionDecisionTransitionService;
                pass the real instance wired to the same store.
        """
        self._store = store if store is not None else LLMAgentTaskRecoveryExecutionPreconditionDecisionStore()
        self._transition_service = (
            transition_service
            if transition_service is not None
            else LLMAgentTaskRecoveryExecutionPreconditionDecisionTransitionService(store=self._store)
        )

    def get_history(self, task_id: str, limit: int = None) -> AgentTaskRecoveryExecutionPreconditionDecisionHistory:
        """task_id's complete decision history, with `decisions` trimmed
        to at most the `limit` most recent records (chronologically
        ordered within that slice) when given.

        Raises:
            InvalidAgentTaskRecoveryExecutionPreconditionDecisionHistoryError:
                If task_id is not a non-empty string, or limit is given
                but is not a positive integer
        """
        self._require_text(task_id, "task_id")
        if limit is not None and (not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0):
            raise InvalidAgentTaskRecoveryExecutionPreconditionDecisionHistoryError(
                "limit must be a positive integer when given"
            )

        full_history = self._store.history(task_id)
        decisions = full_history[-limit:] if limit is not None else full_history

        transitions = tuple(
            self._transition_service.analyze(
                task_id, decision_id=current.decision_id, previous_decision_id=previous.decision_id
            )
            for previous, current in zip(full_history, full_history[1:])
        )

        counts_by_decision = {value: 0 for value in EXECUTION_DECISIONS}
        for entry in full_history:
            counts_by_decision[entry.decision] += 1

        first_decision = full_history[0] if full_history else None
        latest_decision = full_history[-1] if full_history else None

        return AgentTaskRecoveryExecutionPreconditionDecisionHistory(
            task_id=task_id,
            decisions=tuple(decisions),
            first_decision=first_decision,
            latest_decision=latest_decision,
            decision_count=len(full_history),
            counts_by_decision=counts_by_decision,
            transitions=transitions,
            eligibility_change_count=sum(1 for transition in transitions if transition.eligibility_changed),
            review_or_block_transition_count=sum(
                1 for transition in transitions if transition.to_decision != EXECUTION_DECISION_ALLOW
            ),
            current_eligible=latest_decision is not None and latest_decision.decision == EXECUTION_DECISION_ALLOW,
            first_decision_at=first_decision.created_at if first_decision is not None else None,
            last_decision_at=latest_decision.created_at if latest_decision is not None else None,
            generated_at=self._now(),
        )

    def summarize(self, task_id: str) -> AgentTaskRecoveryExecutionPreconditionDecisionHistorySummary:
        """task_id's compact decision-history rollup -- built entirely on
        top of get_history() (Rule: "Do not duplicate decision/comparison
        logic"), never a second aggregation pass over the store.

        Raises:
            InvalidAgentTaskRecoveryExecutionPreconditionDecisionHistoryError:
                If task_id is not a non-empty string
        """
        history = self.get_history(task_id)
        return AgentTaskRecoveryExecutionPreconditionDecisionHistorySummary(
            task_id=task_id,
            decision_count=history.decision_count,
            counts_by_decision=history.counts_by_decision,
            eligibility_change_count=history.eligibility_change_count,
            review_or_block_transition_count=history.review_or_block_transition_count,
            current_eligible=history.current_eligible,
            latest_decision=history.latest_decision,
            first_decision_at=history.first_decision_at,
            last_decision_at=history.last_decision_at,
            generated_at=self._now(),
        )

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryExecutionPreconditionDecisionHistoryError(
                f"{field_name} is required and must be a non-empty string"
            )
