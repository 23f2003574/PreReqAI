from datetime import datetime, timezone

from .decision_history import LLMAgentTaskRecoveryExecutionPreconditionDecisionHistoryService
from .models import AgentTaskRecoveryExecutionPreconditionDecisionReport


class InvalidAgentTaskRecoveryExecutionPreconditionDecisionReportError(ValueError):
    """Raised when report() is given invalid arguments."""


class LLMAgentTaskRecoveryExecutionPreconditionDecisionReportingService:
    """A compact, machine-readable, task-level operational report over
    Commit #10's own decision history -- never a second history/
    aggregation engine (Rule: "Do not invent reporting infrastructure or
    duplicate history/transition logic"): report() calls
    LLMAgentTaskRecoveryExecutionPreconditionDecisionHistoryService.
    get_history() exactly once and reshapes its own already-computed
    fields into a report; it never reruns validate()/classify()/
    reconcile()/decide() and never persists anything of its own (Rule:
    "Do not introduce a second persistence layer").

    Deliberately not analytics (Rule: "Do not turn this into analytics;
    this is a task-level operational report"): every field describes
    exactly ONE task's own current state and history, never a cross-task
    aggregate, rate, or trend.

    Read-only (Rule): report() only ever reads through get_history().

    Deterministic (Rule): Commit #10's own get_history() is already
    deterministic over fixed input, so calling report() twice in a row
    with nothing else changed always returns an identical report.
    """

    def __init__(self, history_service: LLMAgentTaskRecoveryExecutionPreconditionDecisionHistoryService = None):
        """
        Args:
            history_service: Defaults to a fresh
                LLMAgentTaskRecoveryExecutionPreconditionDecisionHistoryService;
                pass the real instance wired to the same decision store.
        """
        self._history_service = (
            history_service
            if history_service is not None
            else LLMAgentTaskRecoveryExecutionPreconditionDecisionHistoryService()
        )

    def report(self, task_id: str, limit: int = None) -> AgentTaskRecoveryExecutionPreconditionDecisionReport:
        """task_id's compact operational report, with its own
        decision_history trimmed the same way Commit #10's own
        get_history(limit=...) trims `decisions`.

        Raises:
            InvalidAgentTaskRecoveryExecutionPreconditionDecisionReportError:
                If task_id is not a non-empty string, or limit is given
                but is not a positive integer (Commit #10's own
                get_history() raises for either)
        """
        try:
            history = self._history_service.get_history(task_id, limit=limit)
        except ValueError as error:
            raise InvalidAgentTaskRecoveryExecutionPreconditionDecisionReportError(str(error)) from error

        latest_transition = history.transitions[-1] if history.transitions else None
        latest_decision = history.latest_decision

        return AgentTaskRecoveryExecutionPreconditionDecisionReport(
            task_id=task_id,
            latest_decision=latest_decision,
            latest_decision_at=history.last_decision_at,
            current_eligible=history.current_eligible,
            decision_count=history.decision_count,
            counts_by_decision=history.counts_by_decision,
            transition_count=len(history.transitions),
            eligibility_change_count=history.eligibility_change_count,
            review_or_block_transition_count=history.review_or_block_transition_count,
            latest_transition=latest_transition,
            material_changes=latest_transition.material_changes if latest_transition is not None else (),
            blocking_conditions=latest_decision.blocking_conditions if latest_decision is not None else (),
            warnings=latest_decision.warnings if latest_decision is not None else (),
            decision_history=history.decisions,
            generated_at=self._now(),
        )

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)
