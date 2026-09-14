from typing import Optional

from backend.llm.secret_redaction import LLMSecretRedactionService

from .in_memory_store import InMemoryAgentTaskEventStore
from .models import AgentTaskEvent
from .store import AgentTaskEventStore

# Module-level, stateless, the same reuse convention
# backend.agent_capability_execution/backend.agent_task_context_integrity
# already use for this exact service -- LLMSecretRedactionService needs no
# store, so there is never a reason for two instances of it in this module.
_redactor = LLMSecretRedactionService()


class InvalidAgentTaskEventError(ValueError):
    """Raised when emit()/get()/latest() is given invalid arguments."""


class LLMAgentTaskEventService:
    """Durable, append-only event stream for meaningful AgentTask changes --
    kept entirely decoupled from the services that actually own those
    changes (backend.agent_task_lifecycle, backend.agent_task_dependencies,
    backend.agent_task_readiness, backend.agent_task_queue_retry_scheduler,
    backend.agent_task_context, and their own history/state), the same
    "the entity service never records its own history; a separate service
    does" split backend.agent_task_state_history.
    LLMAgentTaskStateHistoryService already establishes for Commit #1's
    own AgentTask transitions (see backend.agent_task_state_history.tracked
    for the shape a future commit's own tracked-style wrapper around this
    service would take).

    This is not a second, competing history/audit framework (Rule: "Do not
    invent a second event bus or generic audit framework") -- it holds no
    opinion on task identity (like LLMAgentTaskStateHistoryService, it
    never calls into backend.agent_task_lifecycle to confirm a task_id
    exists) and never itself judges whether an event "should" have
    happened; a caller is responsible for only ever calling emit() for a
    change that actually occurred (Rule: "Event emission must be
    deterministic and testable" -- emit() performs no side effects beyond
    appending the one record it was asked to append).

    emit()/get()/latest() mirror LLMAgentTaskStateHistoryService's own
    record_transition()/get_history()/get_latest() shape (query surface a
    plain append-only store never exposes on its own), generalized from
    "lifecycle transitions only" to any of this family's meaningful event
    kinds -- see .models.KNOWN_EVENT_TYPES for the documented (not
    enforced) vocabulary.
    """

    def __init__(self, store: AgentTaskEventStore = None):
        self.store = store if store is not None else InMemoryAgentTaskEventStore()

    def emit(self, task_id: str, event_type: str, payload: Optional[dict] = None) -> AgentTaskEvent:
        """Append one event for task_id. Append-only: there is no update
        or delete, and every call adds a new entry.

        payload, when given, is redacted through this repository's own
        canonical backend.llm.secret_redaction.LLMSecretRedactionService
        before it is stored (Rule: "Prefer references/metadata over
        duplicating large or sensitive payloads") -- callers should still
        pass small references/metadata rather than a large duplicated
        record, since redaction only screens for known secret patterns,
        it does not shrink or summarize otherwise-large content.

        Raises:
            InvalidAgentTaskEventError: If task_id or event_type is not a
                non-empty string, or payload is given and is not a dict
        """
        self._require_text(task_id, "task_id")
        self._require_text(event_type, "event_type")
        if payload is not None and not isinstance(payload, dict):
            raise InvalidAgentTaskEventError("payload must be a dict when given")

        redacted_payload = _redactor.redact(payload) if payload is not None else None
        event = AgentTaskEvent(task_id=task_id, event_type=event_type, payload=redacted_payload)
        return self.store.save(event)

    def get(self, task_id: str, event_type: str = None, limit: int = None) -> list:
        """task_id's recorded events, oldest to newest, optionally
        narrowed to a single event_type and/or capped to the most recent
        limit entries (still returned oldest to newest).

        Never raises for a task_id with no recorded events: an empty list,
        exactly as for a task_id that was never emitted for at all -- this
        service holds no opinion on task identity, the same discipline
        LLMAgentTaskStateHistoryService.get_history() already establishes.

        Raises:
            InvalidAgentTaskEventError: If task_id is not a non-empty
                string, event_type is given and is not a non-empty string,
                or limit is given and is not a non-negative int
        """
        self._require_text(task_id, "task_id")
        if event_type is not None:
            self._require_text(event_type, "event_type")
        if limit is not None and (not isinstance(limit, int) or isinstance(limit, bool) or limit < 0):
            raise InvalidAgentTaskEventError("limit must be a non-negative int when given")

        events = self.store.list_for_task(task_id)
        if event_type is not None:
            events = [event for event in events if event.event_type == event_type]
        if limit is not None:
            events = events[-limit:] if limit > 0 else []
        return events

    def latest(self, task_id: str, event_type: str = None) -> Optional[AgentTaskEvent]:
        """task_id's most recently recorded event, optionally narrowed to
        a single event_type, or None if there is no such event."""
        events = self.get(task_id, event_type=event_type)
        return events[-1] if events else None

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskEventError(f"{field_name} is required and must be a non-empty string")
