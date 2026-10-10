from typing import Optional

from .models import CONTEXT_UPDATED, RETRY_CANCELLED, RETRY_SCHEDULED, AgentTaskEventProjection
from .projection_in_memory_store import InMemoryAgentTaskEventProjectionStore
from .projection_store import AgentTaskEventProjectionStore
from .query import LLMAgentTaskEventQueryService
from .replay import LLMAgentTaskEventReplayService
from .timeline import LLMAgentTaskEventTimelineService


class InvalidAgentTaskEventProjectionError(ValueError):
    """Raised when project()/refresh()/get() is given invalid arguments."""


class LLMAgentTaskEventProjectionService:
    """Maintains a queryable, current-state read model per task_id,
    derived entirely from Commit #1's own persisted event stream -- the
    first *reusable, queryable* derived view in this series distinct from
    both Commit #3's Timeline (a full chronological trail) and Commit #6's
    Replay (a one-shot "what happened when replayed" answer): a projection
    is the *current* answer, kept around so a caller never has to re-walk
    the whole stream just to ask "what state is this task's event log
    saying right now."

    Composes, never duplicates, three earlier commits (Rule: "Do not
    create another timeline/query implementation"; "Reuse Commit #6
    replay semantics ... instead of duplicating transition logic"):
      - current_state/last_error_reference come from one Commit #6
        LLMAgentTaskEventReplayService.replay() call
      - last_event_id/last_event_at/event_count come from one Commit #3
        LLMAgentTaskEventTimelineService.build() call
      - active_retry_reference/active_context_reference are derived by a
        single backward scan over that same Timeline's own already-
        ordered events -- no new query or sort of any kind
    Nothing here re-implements chronological ordering, transition
    legality, or event filtering; every one of those questions is asked
    of the commit that already owns the answer.

    project()/refresh()/get() are three distinct operations (a real
    design choice: the closest existing precedent,
    backend.agent_task_readiness_projection.
    LLMAgentTaskReadinessProjectionService, conflates "compute" and
    "persist" into one project() call; this goal names three, so they
    stay distinct here):
      - project() is a pure computation -- it never touches self.store,
        so calling it repeatedly can never leave stale data behind
        because it never leaves any data behind at all.
      - refresh() is project() plus a self.store.save() -- the one
        method that actually materializes/replaces the persisted view
        (Behavior: "rebuilds and persists/replaces the derived
        projection").
      - get() is a plain self.store.get() -- it never replays or
        queries events itself (Behavior: "reads the existing projection
        without replaying events"), and therefore never detects
        staleness on its own; a caller who needs a guaranteed-fresh view
        calls refresh() (or compares the returned projection's own
        event_count against LLMAgentTaskEventQueryService.count(task_id)
        -- see AgentTaskEventProjection's own docstring for why no
        second staleness field was added for this).

    Deterministic (Rule: "Projection updates must be deterministic";
    "Re-projecting the same event stream produces the same result"):
    project()/refresh() only ever read through query_service/
    timeline_service/replay_service, each already deterministic over a
    fixed event stream, and never consult wall-clock time or randomness
    for anything but this result's own bookkeeping evaluated_at.

    Read-only with respect to the task and its events (Rule): nothing
    here ever calls emit()/transition()/update() on any collaborator --
    the only thing refresh() ever writes to is this service's own
    projection store.
    """

    def __init__(
        self,
        query_service: LLMAgentTaskEventQueryService = None,
        timeline_service: LLMAgentTaskEventTimelineService = None,
        replay_service: LLMAgentTaskEventReplayService = None,
        store: AgentTaskEventProjectionStore = None,
    ):
        self._query_service = query_service if query_service is not None else LLMAgentTaskEventQueryService()
        self._timeline_service = (
            timeline_service if timeline_service is not None else LLMAgentTaskEventTimelineService(self._query_service)
        )
        self._replay_service = (
            replay_service if replay_service is not None else LLMAgentTaskEventReplayService(self._query_service)
        )
        self.store = store if store is not None else InMemoryAgentTaskEventProjectionStore()

    def project(self, task_id: str) -> AgentTaskEventProjection:
        """Rebuild task_id's projection from its current event stream.
        Purely computed: never reads or writes self.store, so calling
        this alone never changes what get() later returns.

        Never raises for a task_id with no recorded events: a clean,
        fully-populated projection (current_state=CREATED, event_count=0,
        every reference field None) -- this service holds no opinion on
        task identity, the same discipline every other read path in this
        family already establishes.

        Raises:
            InvalidAgentTaskEventProjectionError: If task_id is not a
                non-empty string
        """
        if not task_id or not isinstance(task_id, str):
            raise InvalidAgentTaskEventProjectionError("task_id is required and must be a non-empty string")

        timeline = self._timeline_service.build(task_id)
        replay_result = self._replay_service.replay(task_id)

        last_event = timeline.events[-1] if timeline.events else None
        last_error = replay_result.replay_errors[-1] if replay_result.replay_errors else None

        return AgentTaskEventProjection(
            task_id=task_id,
            current_state=replay_result.final_state,
            last_event_id=last_event.event_id if last_event is not None else None,
            last_event_at=timeline.last_event_at,
            event_count=timeline.event_count,
            last_error_reference=last_error.event_id if last_error is not None else None,
            active_retry_reference=self._active_retry_reference(timeline.events),
            active_context_reference=self._active_context_reference(timeline.events),
        )

    def refresh(self, task_id: str) -> AgentTaskEventProjection:
        """Rebuild task_id's projection (exactly as project() would) and
        replace whatever was previously stored for it -- the one method
        that actually materializes a persisted, get()-able view.

        Raises:
            InvalidAgentTaskEventProjectionError: If task_id is not a
                non-empty string
        """
        projection = self.project(task_id)
        return self.store.save(projection)

    def get(self, task_id: str) -> Optional[AgentTaskEventProjection]:
        """task_id's last refresh()ed projection, or None if refresh()
        was never called for it. Never replays or queries events itself
        -- a plain store read.

        Raises:
            InvalidAgentTaskEventProjectionError: If task_id is not a
                non-empty string
        """
        if not task_id or not isinstance(task_id, str):
            raise InvalidAgentTaskEventProjectionError("task_id is required and must be a non-empty string")
        return self.store.get(task_id)

    @staticmethod
    def _active_retry_reference(events) -> Optional[str]:
        for event in reversed(events):
            if event.event_type == RETRY_SCHEDULED:
                return event.event_id
            if event.event_type == RETRY_CANCELLED:
                return None
        return None

    @staticmethod
    def _active_context_reference(events) -> Optional[str]:
        for event in reversed(events):
            if event.event_type == CONTEXT_UPDATED:
                return event.event_id
        return None
