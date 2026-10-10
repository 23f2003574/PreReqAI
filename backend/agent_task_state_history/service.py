from datetime import datetime
from typing import Optional

from backend.agent_task_lifecycle import STATES

from .in_memory_store import InMemoryAgentTaskTransitionStore
from .models import TaskTransitionRecord
from .store import AgentTaskTransitionStore


class InvalidTaskTransitionRecordError(ValueError):
    """Raised when record_transition()/get_history() is given invalid
    arguments."""


class LLMAgentTaskStateHistoryService:
    """Durable, queryable history of Commit #1 AgentTask transitions --
    kept entirely separate from backend.agent_task_lifecycle.
    LLMAgentTaskLifecycleService itself, so that service can go on owning
    only *whether* a transition is valid and *performing* it, never how
    or whether it gets recorded. The same "the entity service never
    records its own history; a separate service does" split
    backend.agent_policy_history.LLMAgentPolicyHistoryService already
    establishes for backend.agent_policy_engine.LLMAgentPolicyService --
    see .tracked.LLMAgentTaskLifecycleHistoryTrackedService for the thin
    wrapper that actually calls record_transition() after each of
    Commit #1's own create()/transition() calls succeeds.

    Reuses Commit #1's own STATES vocabulary (to validate against) and
    this module's own TaskTransitionRecord/AgentTaskTransitionStore --
    not a second, competing history record shape or a generic event/
    audit framework, just the query/record surface a plain append-only
    store never exposes on its own.

    record_transition() never itself judges whether a transition was
    legal -- Commit #1's own LLMAgentTaskLifecycleService.transition()
    (and can_transition()) already owns that, and is the only thing
    .tracked's wrapper ever calls before recording. A rejected/invalid
    Commit #1 transition therefore never reaches this service at all,
    so it can never become a history entry (Rule: "Failed/invalid
    transitions must not create successful transition records").
    """

    def __init__(self, store: AgentTaskTransitionStore = None):
        self.store = store if store is not None else InMemoryAgentTaskTransitionStore()

    def record_transition(
        self, task_id: str, from_state: Optional[str], to_state: str, reason: str = None
    ) -> TaskTransitionRecord:
        """Append one transition record. Append-only: there is no update
        or delete, and every call adds a new entry -- callers (see
        .tracked) are responsible for only ever calling this for a
        transition that actually happened.

        Raises:
            InvalidTaskTransitionRecordError: If task_id is not a
                non-empty string, to_state is not one of Commit #1's own
                STATES, from_state is given and is not one of STATES, or
                reason is given and is not a string
        """
        self._require_task_id(task_id)
        if to_state not in STATES:
            raise InvalidTaskTransitionRecordError(f"to_state {to_state!r} is not one of {sorted(STATES)}")
        if from_state is not None and from_state not in STATES:
            raise InvalidTaskTransitionRecordError(f"from_state {from_state!r} is not one of {sorted(STATES)}")
        if reason is not None and not isinstance(reason, str):
            raise InvalidTaskTransitionRecordError("reason must be a string when given")

        record = TaskTransitionRecord(task_id=task_id, from_state=from_state, to_state=to_state, reason=reason)
        return self.store.save(record)

    def get_history(
        self, task_id: str, to_state: str = None, since: datetime = None, until: datetime = None
    ) -> list:
        """task_id's transition history, oldest first (preserved
        chronological ordering -- see this module's own store). Optional
        filters narrow the result to entries whose to_state matches
        and/or whose occurred_at falls within [since, until] (either
        bound may be omitted) -- the same optional-filter shape
        backend.agent_policy_templates.LLMAgentPolicyTemplateStore.list(
        status=None) and backend.agent_policy_history.
        LLMAgentPolicyHistoryService.get_at()'s own datetime comparison
        already use elsewhere in this repository, rather than a new
        query mechanism.

        Never raises for a task_id with no recorded history: an empty
        list, exactly as for any task_id that was never created at all
        -- this service holds no opinion on task identity, which
        remains entirely Commit #1's own.

        Raises:
            InvalidTaskTransitionRecordError: If task_id is not a
                non-empty string, to_state is given and is not one of
                STATES, or since/until is given and is not a datetime
        """
        self._require_task_id(task_id)
        if to_state is not None and to_state not in STATES:
            raise InvalidTaskTransitionRecordError(f"to_state {to_state!r} is not one of {sorted(STATES)}")
        if since is not None and not isinstance(since, datetime):
            raise InvalidTaskTransitionRecordError("since must be a datetime when given")
        if until is not None and not isinstance(until, datetime):
            raise InvalidTaskTransitionRecordError("until must be a datetime when given")

        records = self.store.list_for_task(task_id)
        if to_state is not None:
            records = [record for record in records if record.to_state == to_state]
        if since is not None:
            records = [record for record in records if record.occurred_at >= since]
        if until is not None:
            records = [record for record in records if record.occurred_at <= until]
        return records

    def get_latest(self, task_id: str) -> Optional[TaskTransitionRecord]:
        """The most recent (unfiltered) transition record for task_id,
        or None if task_id has no recorded history."""
        history = self.get_history(task_id)
        return history[-1] if history else None

    @staticmethod
    def _require_task_id(task_id) -> None:
        if not task_id or not isinstance(task_id, str):
            raise InvalidTaskTransitionRecordError("task_id is required and must be a non-empty string")
