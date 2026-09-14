from datetime import datetime

from .in_memory_store import InMemoryAgentTaskEventStore
from .models import (
    AgentTaskArchiveRestoreResult,
    AgentTaskEventArchiveResult,
    AgentTaskEventRetentionCandidate,
)
from .query import LLMAgentTaskEventQueryService
from .retention import LLMAgentTaskEventRetentionService
from .store import AgentTaskEventStore


class InvalidAgentTaskEventArchiveError(ValueError):
    """Raised when archive()/list_archived()/restore() is given invalid
    arguments."""


class LLMAgentTaskEventArchiveService:
    """Moves events Commit #9 already deems eligible for removal out of
    the active event stream into a separate, durable archive store, so
    they remain inspectable without staying in the hot path -- not a
    generic archival framework (Rule): this module's own existing
    AgentTaskEventStore ABC (Commit #1) already fits perfectly (save()/
    list_for_task()/all()/delete(), the exact shape both the active and
    archive stores need), so archive_store is simply a *second instance*
    of the same InMemoryAgentTaskEventStore/JsonAgentTaskEventStore
    classes Commit #1 already provides -- no new store type is declared
    anywhere in this module.

    Reuses Commit #9's own eligibility rules verbatim (Rule: "Reuse
    Commit #9 retention eligibility rather than implementing competing
    rules"): archive() never re-derives which events are old enough or
    still protected -- it calls retention_service.plan()/execute() and
    only ever archives what execute() actually removed. This also means
    every one of Commit #9's own four protections (latest event, stale
    projection reference, active/incomplete task, referenced parent)
    transparently protects an event from archival too, with zero
    duplicated logic.

    list_archived() reuses Commit #2's own LLMAgentTaskEventQueryService
    unchanged, simply constructed over archive_store instead of the
    active store (Rule: "Do not duplicate the event query service") --
    there is no second filtering/sorting/pagination implementation
    anywhere in this module.

    Archived events remain distinguishable from active ones purely by
    which store currently holds them (Rule) -- AgentTaskEvent itself
    gains no "archived" flag or second representation; an event is
    archived exactly when it is absent from the active store and present
    in archive_store. Because Commits #3/#6/#7's own query_service/
    timeline_service/replay_service/projection_service are all
    constructed over the *active* store by default, an archived event is
    automatically invisible to ordinary projection/replay/timeline
    computation the moment it moves -- until restore() moves it back
    (Rule: "must not be treated as active projection input unless
    explicitly restored"). No code in those other modules changes at all.

    restore() bypasses Commit #1's own emit() entirely and calls the
    active store's save() directly with the exact archived AgentTaskEvent
    object -- emit() would mint a *new* event_id/occurred_at, which would
    violate "Archiving must not change event identity or chronological
    meaning"; store.save() preserves every field of the object it is
    given verbatim.

    Never touches backend.agent_task_lifecycle at all (Rule: "Do not
    modify authoritative task state") -- only retention_service (which
    itself, per its own docstring, only ever reads lifecycle state when
    supplied one) and two AgentTaskEventStore instances are involved.
    """

    def __init__(
        self,
        retention_service: LLMAgentTaskEventRetentionService = None,
        archive_store: AgentTaskEventStore = None,
    ):
        self._retention_service = (
            retention_service if retention_service is not None else LLMAgentTaskEventRetentionService()
        )
        self.archive_store = archive_store if archive_store is not None else InMemoryAgentTaskEventStore()
        self._archive_query_service = LLMAgentTaskEventQueryService(store=self.archive_store)

    def archive(self, task_id: str, before: datetime = None) -> AgentTaskEventArchiveResult:
        """Move every currently-eligible (per Commit #9's own rules) event
        of task_id from the active store into the archive store.

        Handles a task with nothing eligible cleanly: an empty result,
        never an error. Idempotent (Rule): once an event has been moved,
        it no longer exists in the active store, so a later plan() for
        the same task_id never proposes it again -- repeated archive()
        calls settle to a no-op with nothing new to move.

        Raises:
            InvalidAgentTaskEventArchiveError: If task_id is not a
                non-empty string
        """
        self._require_text(task_id)

        plan = self._retention_service.plan(task_id, before=before)
        if not plan.eligible:
            return AgentTaskEventArchiveResult(
                task_id=task_id, before=plan.before, archived=(), already_archived=(), skipped=()
            )

        # Fetched before execute() runs -- once execute() deletes a candidate
        # it can no longer be read back from the active store.
        events_by_id = {event.event_id: event for event in self._retention_service.query_service.query(task_id=task_id)}

        result = self._retention_service.execute(plan)

        archived = []
        for candidate in result.removed:
            event = events_by_id.get(candidate.event_id)
            if event is not None:
                self.archive_store.save(event)
                archived.append(candidate)

        already_archived = tuple(
            AgentTaskEventRetentionCandidate(task_id=c.task_id, event_id=c.event_id) for c in result.already_removed
        )

        return AgentTaskEventArchiveResult(
            task_id=task_id,
            before=plan.before,
            archived=tuple(archived),
            already_archived=already_archived,
            skipped=result.newly_protected,
        )

    def list_archived(
        self, task_id: str, start_time: datetime = None, end_time: datetime = None, limit: int = None
    ) -> list:
        """task_id's archived events, oldest to newest, optionally
        narrowed exactly the way Commit #2's own query() already
        supports -- read-only.

        Raises the same errors Commit #2's own query() raises for these
        arguments.
        """
        return self._archive_query_service.query(
            task_id=task_id, start_time=start_time, end_time=end_time, limit=limit
        )

    def restore(self, task_id: str, event_ids: list = None) -> AgentTaskArchiveRestoreResult:
        """Move task_id's archived events (or only the given event_ids,
        when supplied) back into the active store, preserving their exact
        original identity and timestamps.

        Never creates a duplicate identity (Rule): an event_id already
        present in the active store is left alone and reported in
        already_restored, never re-inserted.

        Raises:
            InvalidAgentTaskEventArchiveError: If task_id is not a
                non-empty string, or event_ids is given and is not a
                list or tuple
        """
        self._require_text(task_id)
        if event_ids is not None and not isinstance(event_ids, (list, tuple)):
            raise InvalidAgentTaskEventArchiveError("event_ids must be a list or tuple when given")

        archived_events = self._archive_query_service.query(task_id=task_id)

        not_found = ()
        if event_ids is not None:
            requested = list(dict.fromkeys(event_ids))
            found_ids = {event.event_id for event in archived_events}
            archived_events = [event for event in archived_events if event.event_id in requested]
            not_found = tuple(event_id for event_id in requested if event_id not in found_ids)

        active_store = self._retention_service.query_service.store
        active_event_ids = {event.event_id for event in active_store.list_for_task(task_id)}

        restored = []
        already_restored = []
        for event in archived_events:
            if event.event_id in active_event_ids:
                already_restored.append(AgentTaskEventRetentionCandidate(task_id=event.task_id, event_id=event.event_id))
                continue
            active_store.save(event)
            self.archive_store.delete(event.task_id, event.event_id)
            restored.append(AgentTaskEventRetentionCandidate(task_id=event.task_id, event_id=event.event_id))

        return AgentTaskArchiveRestoreResult(
            task_id=task_id,
            restored=tuple(restored),
            already_restored=tuple(already_restored),
            not_found=not_found,
        )

    @staticmethod
    def _require_text(task_id) -> None:
        if not task_id or not isinstance(task_id, str):
            raise InvalidAgentTaskEventArchiveError("task_id is required and must be a non-empty string")
