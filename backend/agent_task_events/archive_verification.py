from datetime import datetime

from .archive import LLMAgentTaskEventArchiveService
from .models import AgentTaskArchiveMismatch, AgentTaskEventArchiveVerificationResult
from .query import LLMAgentTaskEventQueryService
from .replay import LLMAgentTaskEventReplayService


class InvalidAgentTaskEventArchiveVerificationError(ValueError):
    """Raised when verify() is given invalid arguments."""


class LLMAgentTaskEventArchiveVerificationService:
    """Audits Commit #10's own archive/active split for one task_id --
    never a second validation/audit framework (Rule): every check here
    either reuses an existing collaborator directly (Commit #10's own
    archive_service.list_archived(), Commit #6's own
    LLMAgentTaskEventReplayService) or is a small, purpose-built
    comparison over the plain AgentTaskEvent fields Commits #1/#4 already
    persist -- never a re-derivation of anything Commit #5's own
    LLMAgentTaskEventConsistencyService, Commit #6's replay, or Commit
    #9/#10's own eligibility/archival logic already computes.

    Read-only (Rule): verify() never calls emit()/save()/delete()/
    restore() on anything -- it only ever reads through
    archive_service.list_archived(), an active-store query_service, and a
    replay_service bound to the archive store.

    "Do not compare fields the repository does not actually persist"
    shaped this service's own scope directly: Commit #10's archive()
    *moves* an event rather than duplicating it, so there is no
    durable "original" snapshot anywhere to diff an archived copy
    against after the fact (an AgentTaskEventArchiveResult is returned
    once, by that one archive() call, and never itself persisted).
    Verification is therefore necessarily about **internal** consistency
    of what the two stores currently hold, not a before/after diff:
      - event identity/task/type/timestamp "preserved" means well-formed
        and internally coherent (event_type/occurred_at/payload are the
        right type; the event's own task_id field agrees with the
        task_id it is filed under) -- not a comparison against a vanished
        pre-archival value that was never retained anywhere.
      - correlation/parent relationships reuse the same three checks
        Commit #5's own INVALID_RELATIONSHIP category already established
        (missing parent, self-reference, parent occurring after its
        child, correlation mismatch with the resolved parent) -- rewritten
        here, not called into Commit #5 directly, because Commit #5's own
        service is bound to one single query_service/store, while this
        check must resolve a parent that may legitimately live in either
        store (an archived child's own parent is very often still active,
        per Commit #9's own "referenced parent is always protected"
        rule) -- a merged, read-only lookup dict, never a new store or
        query abstraction.
      - replayability is confirmed by actually calling Commit #6's own
        LLMAgentTaskEventReplayService.replay() against a query_service
        bound to the archive store: reaching a result without raising is
        the check. A pre-existing replay_errors entry in the historical
        stream is not itself treated as an archival defect (that
        inconsistency existed before archival moved anything, and Commit
        #5 already owns judging event-stream validity on its own terms).
      - "archived event count matches the archive operation" is honored
        via the event_ids parameter: a caller who kept the event_ids an
        AgentTaskEventArchiveResult.archived just named can pass them
        straight back in to confirm every one of them still exists
        somewhere and was not lost or duplicated.

    duplicate_events/missing_events are reported, never fixed (Rule: "Do
    not mutate or repair data") -- this service has no write path at all.
    """

    def __init__(
        self,
        archive_service: LLMAgentTaskEventArchiveService = None,
        active_query_service: LLMAgentTaskEventQueryService = None,
        replay_service: LLMAgentTaskEventReplayService = None,
    ):
        self._archive_service = (
            archive_service if archive_service is not None else LLMAgentTaskEventArchiveService()
        )
        self._active_query_service = (
            active_query_service if active_query_service is not None else LLMAgentTaskEventQueryService()
        )
        self._replay_service = (
            replay_service
            if replay_service is not None
            else LLMAgentTaskEventReplayService(
                LLMAgentTaskEventQueryService(store=self._archive_service.archive_store)
            )
        )

    def verify(self, task_id: str, event_ids: list = None) -> AgentTaskEventArchiveVerificationResult:
        """Verify task_id's archived events (or only event_ids, when
        given) are complete and internally consistent.

        Handles an empty archive cleanly: checked_count=0, every
        collection empty, is_valid=True -- there is nothing to be wrong
        about yet.

        Raises:
            InvalidAgentTaskEventArchiveVerificationError: If task_id is
                not a non-empty string, or event_ids is given and is not
                a list or tuple
        """
        self._require_text(task_id)
        if event_ids is not None and not isinstance(event_ids, (list, tuple)):
            raise InvalidAgentTaskEventArchiveVerificationError("event_ids must be a list or tuple when given")

        archived_events = {event.event_id: event for event in self._archive_service.list_archived(task_id)}
        active_events = {event.event_id: event for event in self._active_query_service.query(task_id=task_id)}
        combined = {**active_events, **archived_events}

        target_ids = list(dict.fromkeys(event_ids)) if event_ids is not None else list(archived_events.keys())

        missing = []
        duplicates = []
        mismatches = []

        for event_id in target_ids:
            in_archive = event_id in archived_events
            in_active = event_id in active_events

            if not in_archive and not in_active:
                missing.append(event_id)
                continue

            if in_archive and in_active:
                duplicates.append(event_id)

            if in_archive:
                event = archived_events[event_id]
                mismatches.extend(self._check_well_formed(event, task_id))
                mismatches.extend(self._check_relationship(event, combined))

        # Replayability: confirmed simply by reaching past this call without
        # an exception -- a pre-existing replay_errors entry is not itself
        # treated as an archival defect (see this class's own docstring).
        self._replay_service.replay(task_id)

        is_valid = not missing and not duplicates and not mismatches

        return AgentTaskEventArchiveVerificationResult(
            task_id=task_id,
            is_valid=is_valid,
            checked_count=len(target_ids),
            missing_events=tuple(missing),
            mismatches=tuple(mismatches),
            duplicate_events=tuple(duplicates),
        )

    @staticmethod
    def _check_well_formed(event, task_id: str) -> list:
        mismatches = []

        if event.task_id != task_id:
            mismatches.append(
                AgentTaskArchiveMismatch(
                    event_id=event.event_id,
                    field="task_id",
                    reason=f"filed under task_id {task_id!r} but its own task_id field is {event.task_id!r}",
                )
            )

        if not event.event_type or not isinstance(event.event_type, str):
            mismatches.append(
                AgentTaskArchiveMismatch(
                    event_id=event.event_id, field="event_type", reason="missing or non-string event_type"
                )
            )

        if not isinstance(event.occurred_at, datetime):
            mismatches.append(
                AgentTaskArchiveMismatch(
                    event_id=event.event_id, field="occurred_at", reason="missing or non-datetime occurred_at"
                )
            )

        if event.payload is not None and not isinstance(event.payload, dict):
            mismatches.append(
                AgentTaskArchiveMismatch(
                    event_id=event.event_id, field="payload", reason="payload is present but not a dict"
                )
            )

        return mismatches

    @staticmethod
    def _check_relationship(event, combined: dict) -> list:
        if event.parent_event_id is None:
            return []

        if event.parent_event_id == event.event_id:
            return [
                AgentTaskArchiveMismatch(
                    event_id=event.event_id,
                    field="parent_event_id",
                    reason="references itself as its own parent_event_id",
                )
            ]

        parent = combined.get(event.parent_event_id)
        if parent is None:
            return [
                AgentTaskArchiveMismatch(
                    event_id=event.event_id,
                    field="parent_event_id",
                    reason=f"parent_event_id {event.parent_event_id!r} does not exist in either store",
                )
            ]

        mismatches = []
        if parent.occurred_at > event.occurred_at:
            mismatches.append(
                AgentTaskArchiveMismatch(
                    event_id=event.event_id,
                    field="parent_event_id",
                    reason="referenced parent occurred after this event",
                )
            )
        if (
            event.correlation_id is not None
            and parent.correlation_id is not None
            and event.correlation_id != parent.correlation_id
        ):
            mismatches.append(
                AgentTaskArchiveMismatch(
                    event_id=event.event_id,
                    field="correlation_id",
                    reason=f"differs from referenced parent's own correlation_id {parent.correlation_id!r}",
                )
            )
        return mismatches

    @staticmethod
    def _require_text(task_id) -> None:
        if not task_id or not isinstance(task_id, str):
            raise InvalidAgentTaskEventArchiveVerificationError(
                "task_id is required and must be a non-empty string"
            )
