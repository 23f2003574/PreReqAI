from typing import Optional

from .models import (
    RECOVERY_OUTCOME_FAILED,
    RECOVERY_OUTCOME_PARTIAL,
    RECOVERY_OUTCOME_SUCCESS,
    AgentTaskRecoveryHistorySummary,
    AgentTaskRecoveryOutcome,
)
from .recovery_outcome import LLMAgentTaskRecoveryOutcomeService


class InvalidAgentTaskRecoveryHistoryError(ValueError):
    """Raised when get()/latest()/summarize() is given invalid arguments."""


class LLMAgentTaskRecoveryHistoryService:
    """A dedicated, read-only view over Commit #5's own recovery outcomes
    -- never another history/audit framework (Rule): every method here is
    a thin composition of LLMAgentTaskRecoveryOutcomeService.list()/get(),
    never a re-query of backend.agent_task_events directly and never a
    second copy of backend.agent_task_state_history's own trail (Rule: "Do
    not duplicate task state history"; "do not reconstruct them from raw
    events").

    get()/latest() return Commit #5's own AgentTaskRecoveryOutcome objects
    completely unchanged (Rule: "Preserve complete outcome objects when
    returning history") -- this service never reshapes, summarizes, or
    strips a field from one before handing it back; summarize() is the
    only place any aggregation happens, and even there every field is
    either a plain count or a value copied verbatim from the latest
    outcome (see AgentTaskRecoveryHistorySummary's own docstring).

    Deterministic ordering is entirely inherited (Rule): Commit #5's own
    list()/get() are already deterministic (backed by backend.
    agent_task_events' own query() ordering), so this service adds no
    sorting of its own -- get(limit=...) only ever slices the
    already-ordered list Commit #5 returns, the same "most recent N,
    still oldest-to-newest" convention this task family's own event
    services already established.
    """

    def __init__(self, outcome_service: LLMAgentTaskRecoveryOutcomeService = None):
        self._outcome_service = (
            outcome_service if outcome_service is not None else LLMAgentTaskRecoveryOutcomeService()
        )

    def get(self, task_id: str, limit: int = None) -> list:
        """task_id's recorded recovery outcomes, oldest to newest,
        optionally capped to the most recent limit entries (still
        returned oldest to newest).

        Never raises for a task_id with no recovery attempts at all: an
        empty list.

        Raises:
            InvalidAgentTaskRecoveryHistoryError: If task_id is not a
                non-empty string, or limit is given and is not a
                non-negative int
        """
        self._require_text(task_id)
        if limit is not None and (not isinstance(limit, int) or isinstance(limit, bool) or limit < 0):
            raise InvalidAgentTaskRecoveryHistoryError("limit must be a non-negative int when given")

        outcomes = self._outcome_service.list(task_id)
        if limit is not None:
            outcomes = outcomes[-limit:] if limit > 0 else []
        return outcomes

    def latest(self, task_id: str) -> Optional[AgentTaskRecoveryOutcome]:
        """task_id's most recently recorded recovery outcome, or None if
        it has never had one.

        Raises:
            InvalidAgentTaskRecoveryHistoryError: If task_id is not a
                non-empty string
        """
        self._require_text(task_id)
        return self._outcome_service.get(task_id)

    def summarize(self, task_id: str) -> AgentTaskRecoveryHistorySummary:
        """A compact rollup of task_id's own recovery history -- never
        computed from anything but Commit #5's own already-recorded
        outcomes.

        Handles no recovery attempts cleanly: every count is 0, and
        latest_status/latest_action are both None.

        Raises:
            InvalidAgentTaskRecoveryHistoryError: If task_id is not a
                non-empty string
        """
        self._require_text(task_id)
        outcomes = self._outcome_service.list(task_id)
        latest_outcome = outcomes[-1] if outcomes else None

        return AgentTaskRecoveryHistorySummary(
            task_id=task_id,
            total_attempts=len(outcomes),
            successful_attempts=sum(1 for outcome in outcomes if outcome.status == RECOVERY_OUTCOME_SUCCESS),
            failed_attempts=sum(1 for outcome in outcomes if outcome.status == RECOVERY_OUTCOME_FAILED),
            partial_attempts=sum(1 for outcome in outcomes if outcome.status == RECOVERY_OUTCOME_PARTIAL),
            latest_status=latest_outcome.status if latest_outcome is not None else None,
            latest_action=(
                (latest_outcome.executed_action or latest_outcome.planned_action)
                if latest_outcome is not None
                else None
            ),
        )

    @staticmethod
    def _require_text(task_id) -> None:
        if not task_id or not isinstance(task_id, str):
            raise InvalidAgentTaskRecoveryHistoryError("task_id is required and must be a non-empty string")
