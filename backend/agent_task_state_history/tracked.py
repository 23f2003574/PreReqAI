from backend.agent_task_lifecycle import LLMAgentTaskLifecycleService

from .service import LLMAgentTaskStateHistoryService


class LLMAgentTaskLifecycleHistoryTrackedService(LLMAgentTaskLifecycleService):
    """Commit #1's LLMAgentTaskLifecycleService, unchanged, with exactly
    one more step after create()/transition() succeeds: recording a
    TaskTransitionRecord for it.

    Not a second lifecycle service, and Commit #1 is never modified:
    every method here delegates the entire operation to
    super().create()/super().transition() first, completely unchanged,
    and only afterward records what happened -- the same "delegate
    first, then record, best-effort" shape
    backend.agent_policy_history.tracked.LLMAgentPolicyHistoryTrackedService
    already establishes for backend.agent_policy_engine.
    LLMAgentPolicyService. get()/can_transition() are never wrapped,
    since neither one is ever a change to record.

    Recording is best-effort: a failure in the history store can never
    surface to the caller or undo an already-applied lifecycle
    transition -- "lifecycle transitions remain owned by
    LLMAgentTaskLifecycleService" holds by construction, since the real
    create()/transition() call has already fully completed, successfully,
    by the time any recording code runs.

    transition() only records when super().transition() actually
    changed current_state -- an idempotent repeated call to the state a
    task is already in (Commit #1's own no-op) produces no new history
    entry, the same "record only a meaningful change" discipline
    LLMAgentPolicyHistoryTrackedService already applies to an
    already-ARCHIVED policy's own archive() call. A rejected/invalid
    transition raises out of super().transition() before this class ever
    gets a chance to record anything (Rule: "Failed/invalid transitions
    must not create successful transition records").
    """

    def __init__(self, store=None, history_service: LLMAgentTaskStateHistoryService = None):
        super().__init__(store=store)
        self._history_service = history_service if history_service is not None else LLMAgentTaskStateHistoryService()

    def _safe_record(self, task_id, from_state, to_state, reason) -> None:
        try:
            self._history_service.record_transition(task_id, from_state, to_state, reason=reason)
        except Exception:
            pass

    def create(self, task_definition: dict):
        task = super().create(task_definition)
        self._safe_record(task.task_id, None, task.current_state, None)
        return task

    def transition(self, task_id: str, target_state: str, reason: str = None):
        previous_state = super().get(task_id).current_state
        task = super().transition(task_id, target_state, reason=reason)
        if task.current_state != previous_state:
            self._safe_record(task_id, previous_state, task.current_state, reason)
        return task
