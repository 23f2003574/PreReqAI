from datetime import datetime, timedelta, timezone
from typing import Optional

from backend.agent_task_lifecycle import TERMINAL_STATES, LLMAgentTaskLifecycleService, UnknownAgentTaskError

from .models import (
    AgentTaskEventRetentionCandidate,
    AgentTaskEventRetentionPlan,
    AgentTaskEventRetentionProtection,
    AgentTaskEventRetentionResult,
)
from .projection import LLMAgentTaskEventProjectionService
from .query import LLMAgentTaskEventQueryService

# The same default this repository's own closest existing retention
# precedent, backend.llm.observability_retention.DEFAULT_RETENTION, already
# uses -- reused verbatim rather than picking a new number (Rule: "reuse
# existing ... configuration conventions").
DEFAULT_RETENTION_WINDOW = timedelta(days=30)


class InvalidAgentTaskEventRetentionError(ValueError):
    """Raised when plan()/execute() is given invalid arguments."""


class LLMAgentTaskEventRetentionService:
    """Bounds Commit #1's own event stream by removing old events that
    nothing still needs -- never a second retention framework (Rule: "Do
    not invent a second retention framework"; "Do not duplicate generic
    observability retention"): backend.llm.observability_retention.
    LLMObservabilityRetentionService already owns purge_before()-style
    retention for a completely different subsystem (LLM usage/cost/
    latency/error records); this service is scoped only to
    backend.agent_task_events' own AgentTaskEvent stream, reuses that
    module's own DEFAULT_RETENTION value for its default window, and adds
    exactly one new storage capability -- this module's own
    AgentTaskEventStore.delete() (Rule: "Reuse existing storage APIs" --
    extend the existing store, never build a second one).

    plan()/execute() mirror the plan-then-apply split this project already
    uses repeatedly for anything that mutates durable state after a
    proposal (e.g. backend.agent_task_queue_retry_repair/
    _repair_execution): plan() is strictly read-only (Rule) -- it never
    calls delete() -- and execute() is the only method that does, and only
    for a plan.eligible entry it re-confirms is still actually eligible
    at the moment it runs (see AgentTaskEventRetentionResult's own
    docstring for why).

    Four protections, each enforced only when this service can actually
    determine it (Rule: "Only enforce protections that the actual
    repository can determine reliably"):
      1. the chronologically latest event recorded for a task -- always
         enforced (needs nothing but this module's own query_service);
         deleting a task's own most recent event would leave Commit #3's
         Timeline/Commit #6's Replay/Commit #7's Projection unable to
         report a `last_event_id`/`last_event_at` at all going forward
         (Rule: "Preserve replay/projection correctness for retained
         data").
      2. the event a task's own persisted Commit #7 AgentTaskEventProjection.
         last_event_id still points to -- only when an optional
         projection_service is supplied (a stale-but-not-yet-reconciled
         projection's own reference must not be allowed to dangle).
      3. every event belonging to a task whose backend.agent_task_lifecycle
         current_state is not yet terminal -- only when an optional
         lifecycle_service is supplied ("active/incomplete tasks" keep
         their full replay chain; a task this service cannot resolve at
         all, or has no lifecycle record, is never treated as "active" by
         this check alone -- Rule: this service holds no opinion on task
         identity beyond what lifecycle_service can actually answer).
      4. any event referenced as some other event's own Commit #4
         parent_event_id -- always enforced (needs nothing but this
         module's own query_service); deleting a still-referenced parent
         would manufacture a brand-new Commit #5 INVALID_RELATIONSHIP
         violation that did not exist before retention ran.

    Never touches backend.agent_task_lifecycle's own AgentTask record
    itself (Rule: "Do not silently alter authoritative task state") --
    lifecycle_service, when supplied, is only ever read via get().
    """

    def __init__(
        self,
        query_service: LLMAgentTaskEventQueryService = None,
        lifecycle_service: LLMAgentTaskLifecycleService = None,
        projection_service: LLMAgentTaskEventProjectionService = None,
        retention_window: timedelta = DEFAULT_RETENTION_WINDOW,
    ):
        self._query_service = query_service if query_service is not None else LLMAgentTaskEventQueryService()
        self._lifecycle_service = lifecycle_service
        self._projection_service = projection_service
        self._retention_window = retention_window

    def plan(self, task_id: str = None, before: datetime = None) -> AgentTaskEventRetentionPlan:
        """Propose which of task_id's events (or every task's, when
        task_id is omitted) are eligible for removal -- read-only, never
        deletes anything.

        before is the cutoff: an event with occurred_at at or before it is
        a candidate -- the same inclusive end_time boundary Commit #2's
        own query() already uses, reused verbatim rather than a second,
        differently-rounded comparison. Defaults to now minus the
        configured retention_window when omitted (Rule: "events inside
        the configured retention window" are never even candidates).

        Raises:
            InvalidAgentTaskEventRetentionError: If task_id is given and
                is not a non-empty string, or before is given and is not
                a datetime
        """
        if task_id is not None:
            self._require_text(task_id)
        if before is not None and not isinstance(before, datetime):
            raise InvalidAgentTaskEventRetentionError("before must be a datetime when given")

        effective_before = before if before is not None else datetime.now(timezone.utc) - self._retention_window

        all_events = self._query_service.query()
        context = self._build_protection_context(all_events)

        candidates = self._query_service.query(task_id=task_id, end_time=effective_before)

        eligible = []
        protected = []
        for event in candidates:
            reason = self._protection_reason(event, context)
            if reason is None:
                eligible.append(AgentTaskEventRetentionCandidate(task_id=event.task_id, event_id=event.event_id))
            else:
                protected.append(
                    AgentTaskEventRetentionProtection(task_id=event.task_id, event_id=event.event_id, reason=reason)
                )

        return AgentTaskEventRetentionPlan(
            task_id=task_id,
            before=effective_before,
            eligible=tuple(eligible),
            protected=tuple(protected),
        )

    def execute(self, plan: AgentTaskEventRetentionPlan) -> AgentTaskEventRetentionResult:
        """Delete every plan.eligible candidate that is still actually
        eligible right now -- re-checking protection status per candidate
        rather than trusting the plan blindly (see this class's own
        docstring). Idempotent: an already-deleted candidate is reported
        in already_removed, never re-deleted or treated as an error.

        Raises:
            InvalidAgentTaskEventRetentionError: If plan is not an
                AgentTaskEventRetentionPlan
        """
        if not isinstance(plan, AgentTaskEventRetentionPlan):
            raise InvalidAgentTaskEventRetentionError("plan must be an AgentTaskEventRetentionPlan")

        all_events = self._query_service.query()
        context = self._build_protection_context(all_events)
        events_by_id = {event.event_id: event for event in all_events}

        removed = []
        already_removed = []
        newly_protected = []

        for candidate in plan.eligible:
            event = events_by_id.get(candidate.event_id)
            if event is not None:
                reason = self._protection_reason(event, context)
                if reason is not None:
                    newly_protected.append(
                        AgentTaskEventRetentionProtection(
                            task_id=candidate.task_id, event_id=candidate.event_id, reason=reason
                        )
                    )
                    continue

            deleted = self._query_service.store.delete(candidate.task_id, candidate.event_id)
            (removed if deleted else already_removed).append(candidate)

        return AgentTaskEventRetentionResult(
            plan=plan,
            removed=tuple(removed),
            already_removed=tuple(already_removed),
            newly_protected=tuple(newly_protected),
        )

    def _build_protection_context(self, all_events) -> dict:
        latest_event_id_by_task = {}
        referenced_as_parent = set()
        for event in all_events:
            latest_event_id_by_task[event.task_id] = event.event_id
            if event.parent_event_id is not None:
                referenced_as_parent.add(event.parent_event_id)

        return {
            "latest_event_id_by_task": latest_event_id_by_task,
            "referenced_as_parent": referenced_as_parent,
            "active_cache": {},
            "projection_cache": {},
        }

    def _protection_reason(self, event, context: dict) -> Optional[str]:
        if context["latest_event_id_by_task"].get(event.task_id) == event.event_id:
            return "latest event recorded for this task"

        if event.event_id in context["referenced_as_parent"]:
            return "referenced as a parent by another event"

        if self._lifecycle_service is not None and self._is_active(event.task_id, context["active_cache"]):
            return "task has not reached a terminal lifecycle state"

        if self._projection_service is not None:
            projection = self._cached_projection(event.task_id, context["projection_cache"])
            if projection is not None and projection.last_event_id == event.event_id:
                return "referenced by the task's own persisted projection"

        return None

    def _is_active(self, task_id: str, cache: dict) -> bool:
        if task_id not in cache:
            try:
                cache[task_id] = self._lifecycle_service.get(task_id).current_state not in TERMINAL_STATES
            except UnknownAgentTaskError:
                cache[task_id] = False
        return cache[task_id]

    def _cached_projection(self, task_id: str, cache: dict):
        if task_id not in cache:
            cache[task_id] = self._projection_service.get(task_id)
        return cache[task_id]

    @staticmethod
    def _require_text(task_id) -> None:
        if not task_id or not isinstance(task_id, str):
            raise InvalidAgentTaskEventRetentionError("task_id is required and must be a non-empty string")
