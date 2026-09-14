from .archive import LLMAgentTaskEventArchiveService
from .archive_verification import LLMAgentTaskEventArchiveVerificationService
from .models import AgentTaskEventRecoveryConflict, AgentTaskEventRecoveryPlan, AgentTaskEventRecoveryResult
from .query import LLMAgentTaskEventQueryService

# All persisted AgentTaskEvent fields relevant to "is this the same event"
# (Commit #1's payload/correlation fields plus Commit #4's own additions) --
# event_id itself is the lookup key, never part of this comparison, and
# evaluated_at-style bookkeeping does not exist on AgentTaskEvent at all
# (unlike AgentTaskEventProjection), so there is nothing here to exclude the
# way Commit #8's own PROJECTION_COMPARISON_FIELDS had to exclude
# evaluated_at.
_IDENTITY_FIELDS = (
    "task_id",
    "event_type",
    "occurred_at",
    "correlation_id",
    "parent_event_id",
    "operation_id",
    "payload",
)


class InvalidAgentTaskEventRecoveryError(ValueError):
    """Raised when plan_restore()/recover() is given invalid arguments."""


class LLMAgentTaskEventArchiveRecoveryService:
    """Turns Commit #10's archive from cold storage into a safe recovery
    path -- never a second event store or recovery framework (Rule): every
    read/write here goes through Commit #10's own archive_service (list_
    archived()/archive_store) and an active-store query_service, and every
    event moved is the exact object Commit #1 already persisted, never
    reconstructed.

    Reuses Commit #10's own move semantics for a successful restore
    (active_store.save() then archive_store.delete()) -- recovering an
    event returns it fully to the active stream, exactly like Commit #10's
    own restore(), so Commit #11's own verify() (which treats an event
    present in *both* stores as a genuine anomaly) keeps meaning what it
    already means without this module teaching it a second, conflicting
    notion of "duplicate."

    plan_restore() is strictly read-only (Rule): it never calls save()/
    delete() on either store. recover() is the only mutating method, and
    it re-derives a fresh plan from the same scope right before acting
    (Rule: "Recovery must be idempotent" -- see AgentTaskEventRecoveryPlan's
    own docstring for why trusting a possibly-stale plan snapshot would be
    wrong), so a caller can hold onto a plan_restore() result as long as
    they like before calling recover() with it.

    Conflict handling is the genuinely new concept this commit adds over
    Commit #10's own simpler restore() (which only ever asked "does this
    event_id exist in the active store," a binary check): whenever an
    event_id is *still* present in the archive **and** already exists in
    the active store, the two copies are compared field-by-field
    (_IDENTITY_FIELDS) -- identical content means nothing is left to do
    (already_active); different content is a genuine conflict (Rule:
    "Never overwrite an existing event with different content") that
    recover() always reports and never touches, in either direction: the
    active copy is left exactly as found, and the archived copy is never
    deleted (Rule: "Do not silently discard conflicts"; "failed recovery
    leaves existing events unchanged").

    Because a successful recover() deletes the archived copy, that
    specific content comparison is only possible while both copies still
    coexist -- for a requested event_id whose archived copy has *already*
    been moved out (by an earlier recover() call), there is nothing left
    to compare against, so an active copy found under that id is simply
    reported as already_active outright (trusted, not re-verified): this
    is exactly the state a caller re-checking with the same
    event_ids they originally asked to restore will see, and it is what
    makes "already-restored events" observable on request even though
    the archive itself no longer holds independent proof.

    recover() ends by calling Commit #11's own
    LLMAgentTaskEventArchiveVerificationService.verify() against the
    post-recovery state and embeds that result directly (Rule: "Reuse
    Commit #11 verification rather than duplicating it") -- there is no
    second consistency check anywhere in this module.

    Never touches backend.agent_task_lifecycle at all (Rule: "Do not
    mutate authoritative task state") -- only two AgentTaskEventStore
    instances and Commit #11's own verification service are involved.
    """

    def __init__(
        self,
        archive_service: LLMAgentTaskEventArchiveService = None,
        active_query_service: LLMAgentTaskEventQueryService = None,
        verification_service: LLMAgentTaskEventArchiveVerificationService = None,
    ):
        self._archive_service = (
            archive_service if archive_service is not None else LLMAgentTaskEventArchiveService()
        )
        self._active_query_service = (
            active_query_service if active_query_service is not None else LLMAgentTaskEventQueryService()
        )
        self._verification_service = (
            verification_service
            if verification_service is not None
            else LLMAgentTaskEventArchiveVerificationService(
                archive_service=self._archive_service, active_query_service=self._active_query_service
            )
        )

    def plan_restore(self, task_id: str, event_ids: list = None) -> AgentTaskEventRecoveryPlan:
        """Propose which of task_id's archived events (or only event_ids,
        when given) can be safely restored, which need no action, and
        which conflict with a different active event sharing the same
        event_id.

        When event_ids is omitted, the scope is every event_id currently
        in the archive. When given, the scope is exactly those ids,
        whether or not each one is still archived -- one already moved
        back to active by an earlier recover() call is reported in
        already_active (see this class's own docstring for why no
        content comparison is possible there), not silently dropped.

        Never restores, deletes, or overwrites anything.

        Raises:
            InvalidAgentTaskEventRecoveryError: If task_id is not a
                non-empty string, or event_ids is given and is not a
                list or tuple
        """
        self._require_text(task_id)
        if event_ids is not None and not isinstance(event_ids, (list, tuple)):
            raise InvalidAgentTaskEventRecoveryError("event_ids must be a list or tuple when given")

        archived_events = {event.event_id: event for event in self._archive_service.list_archived(task_id)}
        active_events = {event.event_id: event for event in self._active_query_service.query(task_id=task_id)}

        requested_event_ids = tuple(dict.fromkeys(event_ids)) if event_ids is not None else None
        scope = requested_event_ids if requested_event_ids is not None else tuple(archived_events.keys())

        available_in_archive = tuple(event_id for event_id in scope if event_id in archived_events)

        already_active = []
        missing = []
        conflicts = []

        for event_id in scope:
            archived_event = archived_events.get(event_id)
            active_event = active_events.get(event_id)

            if archived_event is None and active_event is None:
                continue  # not found anywhere -- nothing this plan can act on or report

            if archived_event is None:
                already_active.append(event_id)  # already moved back previously; nothing left to compare
            elif active_event is None:
                missing.append(event_id)
            elif self._identical(archived_event, active_event):
                already_active.append(event_id)
            else:
                conflicts.append(
                    AgentTaskEventRecoveryConflict(
                        event_id=event_id, reason=self._describe_conflict(archived_event, active_event)
                    )
                )

        resulting_events = list(active_events.values()) + [archived_events[event_id] for event_id in missing]
        resulting_order = tuple(
            event.event_id
            for event in sorted(resulting_events, key=lambda event: (event.occurred_at, event.task_id, event.event_id))
        )

        return AgentTaskEventRecoveryPlan(
            task_id=task_id,
            requested_event_ids=requested_event_ids,
            available_in_archive=available_in_archive,
            already_active=tuple(already_active),
            missing=tuple(missing),
            conflicts=tuple(conflicts),
            resulting_order=resulting_order,
        )

    def recover(self, plan: AgentTaskEventRecoveryPlan) -> AgentTaskEventRecoveryResult:
        """Restore every currently-missing event named by plan's own
        scope (re-derived fresh, not trusted from the plan snapshot --
        see this class's own docstring), preserving original identity,
        timestamps, and correlation/parent metadata. Never touches a
        conflicting event_id in either direction.

        A successful restore moves the event: saved to the active store,
        then deleted from the archive (Commit #10's own restore()
        semantics, reused rather than reinvented).

        Raises:
            InvalidAgentTaskEventRecoveryError: If plan is not an
                AgentTaskEventRecoveryPlan
        """
        if not isinstance(plan, AgentTaskEventRecoveryPlan):
            raise InvalidAgentTaskEventRecoveryError("plan must be an AgentTaskEventRecoveryPlan")

        fresh_plan = self.plan_restore(
            plan.task_id,
            event_ids=list(plan.requested_event_ids) if plan.requested_event_ids is not None else None,
        )

        archived_events = {event.event_id: event for event in self._archive_service.list_archived(plan.task_id)}
        active_store = self._active_query_service.store

        restored = []
        for event_id in fresh_plan.missing:
            event = archived_events.get(event_id)
            if event is None:
                continue
            active_store.save(event)
            self._archive_service.archive_store.delete(event.task_id, event.event_id)
            restored.append(event_id)

        verification = self._verification_service.verify(plan.task_id)

        return AgentTaskEventRecoveryResult(
            task_id=plan.task_id,
            restored=tuple(restored),
            already_restored=fresh_plan.already_active,
            unresolved_conflicts=fresh_plan.conflicts,
            verification=verification,
        )

    @staticmethod
    def _identical(archived_event, active_event) -> bool:
        return all(
            getattr(archived_event, field_name) == getattr(active_event, field_name)
            for field_name in _IDENTITY_FIELDS
        )

    @staticmethod
    def _describe_conflict(archived_event, active_event) -> str:
        differing = [
            field_name
            for field_name in _IDENTITY_FIELDS
            if getattr(archived_event, field_name) != getattr(active_event, field_name)
        ]
        return f"active event content differs from its archived copy in: {', '.join(differing)}"

    @staticmethod
    def _require_text(task_id) -> None:
        if not task_id or not isinstance(task_id, str):
            raise InvalidAgentTaskEventRecoveryError("task_id is required and must be a non-empty string")
