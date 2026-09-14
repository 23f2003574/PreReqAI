from datetime import timedelta

from .failure_classification import LLMAgentTaskEventFailureClassifier
from .models import (
    RECOVERY_OUTCOME_FAILED,
    RECOVERY_OUTCOME_PARTIAL,
    RECOVERY_OUTCOME_SUCCESS,
    AgentTaskRecoveryEffectiveness,
)
from .recovery_history import LLMAgentTaskRecoveryHistoryService


class InvalidAgentTaskRecoveryEffectivenessError(ValueError):
    """Raised when analyze() is given invalid arguments."""


class LLMAgentTaskRecoveryEffectivenessService:
    """Measures whether Commit #4's own recovery attempts actually
    improved a task's outcome -- analytics over Commit #6's own recovery
    history, never a second recovery executor or a second metrics/
    analytics framework (Rule): analyze() never calls plan()/execute()/
    record() on anything, and every aggregation here is a pure function
    of LLMAgentTaskRecoveryHistoryService.get()'s own already-returned
    AgentTaskRecoveryOutcome list.

    Reuses Commit #6 history rather than rebuilding recovery records from
    raw events (Rule): the only collaborator ever queried for attempts is
    LLMAgentTaskRecoveryHistoryService -- this service never touches
    backend.agent_task_events directly.

    Never claims causality beyond what the stored data supports (Rule):
    terminal_failure_after_recovery is None whenever no failure_classifier
    was supplied, rather than guessed from the recovery outcomes alone
    (an outcome's own `success` only says the recovery *mechanism*
    reported success, not that the task's own real, authoritative history
    ultimately avoided a terminal failure for some unrelated reason) --
    when a Commit #2 LLMAgentTaskEventFailureClassifier is supplied, its
    own already-replay-validated terminal_failure answer is reused
    verbatim, never re-derived from Commit #5/#6's own more limited data.

    success_rate/success_rate_by_action are omitted/None rather than 0.0
    when there is nothing to compute a rate over (Rule: "Missing outcome
    boundaries must remain unknown, not fabricated" -- a 0.0 rate would
    misreport "never attempted" as "attempted and always failed").

    Read-only and deterministic (Rule): every computation here is a pure
    function of an already-deterministic input list, with no randomness
    or wall-clock dependency beyond echoing back timestamps Commit #5
    already recorded.
    """

    def __init__(
        self,
        history_service: LLMAgentTaskRecoveryHistoryService = None,
        failure_classifier: LLMAgentTaskEventFailureClassifier = None,
    ):
        self._history_service = (
            history_service if history_service is not None else LLMAgentTaskRecoveryHistoryService()
        )
        self._failure_classifier = failure_classifier

    def analyze(self, task_id: str) -> AgentTaskRecoveryEffectiveness:
        """Compute task_id's own recovery effectiveness from its recorded
        recovery history.

        Never raises for a task_id with no recovery attempts at all: a
        clean, fully-populated result (every count 0, every rate/duration/
        outcome None) -- this service holds no opinion on task identity,
        the same discipline every other read path in this family already
        establishes.

        Raises:
            InvalidAgentTaskRecoveryEffectivenessError: If task_id is not
                a non-empty string
        """
        if not task_id or not isinstance(task_id, str):
            raise InvalidAgentTaskRecoveryEffectivenessError("task_id is required and must be a non-empty string")

        attempts = self._history_service.get(task_id)
        total = len(attempts)

        successful = sum(1 for attempt in attempts if attempt.status == RECOVERY_OUTCOME_SUCCESS)
        failed = sum(1 for attempt in attempts if attempt.status == RECOVERY_OUTCOME_FAILED)
        partial = sum(1 for attempt in attempts if attempt.status == RECOVERY_OUTCOME_PARTIAL)

        success_rate = (successful / total) if total > 0 else None

        attempts_by_action: dict = {}
        successes_by_action: dict = {}
        for attempt in attempts:
            action = attempt.executed_action or attempt.planned_action
            attempts_by_action[action] = attempts_by_action.get(action, 0) + 1
            if attempt.status == RECOVERY_OUTCOME_SUCCESS:
                successes_by_action[action] = successes_by_action.get(action, 0) + 1

        success_rate_by_action = {
            action: successes_by_action.get(action, 0) / count for action, count in attempts_by_action.items()
        }

        failures_followed_by_success = self._count_failures_followed_by_success(attempts)

        terminal_failure_after_recovery = None
        if self._failure_classifier is not None and total > 0:
            classification = self._failure_classifier.classify(task_id)
            terminal_failure_after_recovery = classification.terminal_failure is not None

        average_recovery_duration = (
            sum((attempt.completed_at - attempt.started_at for attempt in attempts), timedelta()) / total
            if total > 0
            else None
        )

        return AgentTaskRecoveryEffectiveness(
            task_id=task_id,
            total_attempts=total,
            successful_attempts=successful,
            failed_attempts=failed,
            partial_attempts=partial,
            success_rate=success_rate,
            attempts_by_action=attempts_by_action,
            success_rate_by_action=success_rate_by_action,
            failures_followed_by_success=failures_followed_by_success,
            terminal_failure_after_recovery=terminal_failure_after_recovery,
            average_recovery_duration=average_recovery_duration,
            latest_outcome=attempts[-1] if attempts else None,
            attempts=tuple(attempts),
        )

    @staticmethod
    def _count_failures_followed_by_success(attempts) -> int:
        attempts_by_failure: dict = {}
        for attempt in attempts:
            if attempt.source_failure_event_id is None:
                continue
            attempts_by_failure.setdefault(attempt.source_failure_event_id, []).append(attempt)

        return sum(
            1
            for group in attempts_by_failure.values()
            if any(attempt.status == RECOVERY_OUTCOME_SUCCESS for attempt in group)
        )
