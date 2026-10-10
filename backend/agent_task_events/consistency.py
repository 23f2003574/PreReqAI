from backend.agent_task_context import LLMAgentTaskContextService, UnknownTaskContextError
from backend.agent_task_lifecycle import STATES, TERMINAL_STATES, LLMAgentTaskLifecycleService
from backend.agent_task_queue_retry_scheduler import LLMAgentTaskRetryScheduler
from backend.agent_task_state_history import LLMAgentTaskStateHistoryService

from .models import (
    CONFLICTING_TERMINAL,
    CONTEXT_UPDATED,
    IMPOSSIBLE_TRANSITION,
    INVALID_ORDER,
    INVALID_RELATIONSHIP,
    LIFECYCLE_TRANSITIONED,
    MISSING_REFERENCE,
    RETRY_CANCELLED,
    RETRY_SCHEDULED,
    STATE_MISMATCH,
    AgentTaskEventConsistencyResult,
    AgentTaskEventConsistencyViolation,
)
from .query import LLMAgentTaskEventQueryService
from .timeline import LLMAgentTaskEventTimelineService


class InvalidAgentTaskEventConsistencyError(ValueError):
    """Raised when validate() is given invalid arguments."""


class LLMAgentTaskEventConsistencyService:
    """Checks whether one task's own persisted event stream is internally
    consistent and agrees with that task's authoritative lifecycle state --
    never a second state machine or audit framework (Rule): every check
    below either (a) delegates the actual legality question to
    backend.agent_task_lifecycle.LLMAgentTaskLifecycleService.
    can_transition() -- the one authoritative transition definition, the
    same reuse backend.agent_task_state_validation.
    LLMAgentTaskStateValidator already established (Rule: "Do not
    duplicate generic task-state validation" -- whole-AgentTask field
    validation is that validator's job, not this service's; this service
    only ever looks at the *event stream*, never re-checks
    task.definition/required-fields/etc itself) -- or (b) reads an
    existing collaborator's own record of truth for a reference an event
    claims (state history, task context, retry schedule), never inventing
    a parallel copy of what that collaborator already owns.

    Read-only: validate() never calls transition()/emit()/update() on any
    collaborator, and never persists a result.

    state_history_service/context_service/retry_scheduler are optional
    (Rule: "Only enforce relationships actually represented by existing
    repository interfaces" + "Do not reject legitimate legacy events
    merely because optional metadata is absent"): each is used only for
    its own MISSING_REFERENCE check, and omitting one simply skips that
    category of check entirely -- the same "optional collaborator; when
    absent, this check simply does not run" discipline
    backend.agent_task_queue_retry_eligibility's own optional
    failure_service already established. DEPENDENCY_ADDED/
    DEPENDENCY_REMOVED events are deliberately never checked against
    backend.agent_task_dependencies: that module keeps only the *current*
    edge set, not a history of edges ever added/removed, and there is no
    established payload key naming *which* edge an event refers to -- so
    there is no existing interface this service could check that against
    without inventing one, which the Rule above forbids.

    query_service defaults to a fresh, empty LLMAgentTaskEventQueryService
    the same way Commit #3's own LLMAgentTaskEventTimelineService does --
    a caller validating real events must pass one bound to the real store,
    exactly the same caveat already accepted throughout this series.
    timeline_service defaults to a fresh LLMAgentTaskEventTimelineService
    built over that same query_service (Commit #3's own current_observed_state
    derivation, reused verbatim for the STATE_MISMATCH check rather than
    re-derived here -- Rule: "Reuse Commit #2 querying and Commit #3/#4
    event structures").
    """

    def __init__(
        self,
        lifecycle_service: LLMAgentTaskLifecycleService,
        query_service: LLMAgentTaskEventQueryService = None,
        timeline_service: LLMAgentTaskEventTimelineService = None,
        state_history_service: LLMAgentTaskStateHistoryService = None,
        context_service: LLMAgentTaskContextService = None,
        retry_scheduler: LLMAgentTaskRetryScheduler = None,
    ):
        self._lifecycle_service = lifecycle_service
        self._query_service = query_service if query_service is not None else LLMAgentTaskEventQueryService()
        self._timeline_service = (
            timeline_service if timeline_service is not None else LLMAgentTaskEventTimelineService(self._query_service)
        )
        self._state_history_service = state_history_service
        self._context_service = context_service
        self._retry_scheduler = retry_scheduler

    def validate(self, task_id: str) -> AgentTaskEventConsistencyResult:
        """Check task_id's own persisted event stream for internal
        consistency and agreement with its authoritative lifecycle state.

        An empty event stream is a fully valid result (checked_event_count
        =0, no violations) -- this service only reports genuine
        inconsistencies, never penalizes a task for having recorded
        nothing yet.

        Raises:
            InvalidAgentTaskEventConsistencyError: If task_id is not a
                non-empty string
            UnknownAgentTaskError: If task_id was never created (Commit
                #1-of-the-lifecycle-series' own
                LLMAgentTaskLifecycleService.get()/error, propagated
                unchanged) -- there is no authoritative state to check
                event-derived state against otherwise
        """
        if not task_id or not isinstance(task_id, str):
            raise InvalidAgentTaskEventConsistencyError("task_id is required and must be a non-empty string")

        task = self._lifecycle_service.get(task_id)
        events = self._query_service.query(task_id=task_id)

        violations = []
        violations.extend(self._check_lifecycle_chain(events))
        violations.extend(self._check_missing_references(task_id, events))
        violations.extend(self._check_state_mismatch(task_id, task, events))
        violations.extend(self._check_relationships(events))

        return AgentTaskEventConsistencyResult(
            task_id=task_id,
            is_consistent=not violations,
            violations=tuple(violations),
            checked_event_count=len(events),
            checked_task_state=task.current_state,
        )

    def _check_lifecycle_chain(self, events) -> list:
        """IMPOSSIBLE_TRANSITION, INVALID_ORDER, and CONFLICTING_TERMINAL
        -- all three read only this event stream's own LIFECYCLE_TRANSITIONED
        events, in the chronological order Commit #2's own query() already
        guarantees.

        An event whose payload lacks a to_state entirely is skipped, never
        flagged (Rule: "Do not reject legitimate legacy events merely
        because optional metadata is absent") -- but a to_state that *is*
        present and is not one of backend.agent_task_lifecycle.STATES is
        flagged: that is malformed data, not merely-absent metadata.
        """
        violations = []
        chain = []  # (event, to_state) for events with a recognized to_state

        for event in events:
            if event.event_type != LIFECYCLE_TRANSITIONED:
                continue
            to_state = event.payload.get("to_state") if isinstance(event.payload, dict) else None
            if to_state is None:
                continue
            if to_state not in STATES:
                violations.append(
                    AgentTaskEventConsistencyViolation(
                        event_id=event.event_id,
                        category=IMPOSSIBLE_TRANSITION,
                        reason=f"declares to_state {to_state!r}, which is not a recognized lifecycle state",
                    )
                )
                continue
            chain.append((event, to_state))

        for (previous_event, previous_state), (current_event, current_state) in zip(chain, chain[1:]):
            if not LLMAgentTaskLifecycleService.can_transition(previous_state, current_state):
                violations.append(
                    AgentTaskEventConsistencyViolation(
                        event_id=current_event.event_id,
                        category=IMPOSSIBLE_TRANSITION,
                        reason=(
                            f"impossible lifecycle transition from {previous_state!r} to {current_state!r} "
                            f"(previous event {previous_event.event_id!r})"
                        ),
                    )
                )

        first_terminal = next(((event, state) for event, state in chain if state in TERMINAL_STATES), None)
        if first_terminal is not None:
            terminal_event, terminal_state = first_terminal
            for event in events:
                if event.occurred_at <= terminal_event.occurred_at:
                    continue
                is_same_terminal_reaffirmation = (
                    event.event_type == LIFECYCLE_TRANSITIONED
                    and isinstance(event.payload, dict)
                    and event.payload.get("to_state") == terminal_state
                )
                if is_same_terminal_reaffirmation:
                    continue
                violations.append(
                    AgentTaskEventConsistencyViolation(
                        event_id=event.event_id,
                        category=INVALID_ORDER,
                        reason=(
                            f"occurred after task reached terminal state {terminal_state!r} "
                            f"at event {terminal_event.event_id!r}"
                        ),
                    )
                )

        terminal_sightings = [(event, state) for event, state in chain if state in TERMINAL_STATES]
        distinct_terminal_states = {state for _, state in terminal_sightings}
        if len(distinct_terminal_states) > 1:
            for event, state in terminal_sightings:
                violations.append(
                    AgentTaskEventConsistencyViolation(
                        event_id=event.event_id,
                        category=CONFLICTING_TERMINAL,
                        reason=(
                            f"reports terminal state {state!r}, conflicting with other reported terminal "
                            f"states {sorted(distinct_terminal_states)}"
                        ),
                    )
                )

        return violations

    def _check_missing_references(self, task_id: str, events) -> list:
        """MISSING_REFERENCE -- only for the categories an optional
        collaborator was actually supplied for."""
        violations = []

        for event in events:
            if event.event_type == LIFECYCLE_TRANSITIONED and self._state_history_service is not None:
                to_state = event.payload.get("to_state") if isinstance(event.payload, dict) else None
                if to_state in STATES and not self._state_history_service.get_history(task_id, to_state=to_state):
                    violations.append(
                        AgentTaskEventConsistencyViolation(
                            event_id=event.event_id,
                            category=MISSING_REFERENCE,
                            reason=f"claims a transition to {to_state!r} but no matching TaskTransitionRecord exists",
                        )
                    )
            elif event.event_type == CONTEXT_UPDATED and self._context_service is not None:
                try:
                    self._context_service.get(task_id)
                except UnknownTaskContextError:
                    violations.append(
                        AgentTaskEventConsistencyViolation(
                            event_id=event.event_id,
                            category=MISSING_REFERENCE,
                            reason="claims a context update but no task context record exists",
                        )
                    )
            elif event.event_type in (RETRY_SCHEDULED, RETRY_CANCELLED) and self._retry_scheduler is not None:
                if self._retry_scheduler.get_retry_schedule(task_id) is None:
                    violations.append(
                        AgentTaskEventConsistencyViolation(
                            event_id=event.event_id,
                            category=MISSING_REFERENCE,
                            reason=f"claims a {event.event_type} but no retry schedule is recorded for this task",
                        )
                    )

        return violations

    def _check_state_mismatch(self, task_id: str, task, events) -> list:
        """STATE_MISMATCH -- reuses Commit #3's own current_observed_state
        derivation verbatim (never re-derived here), compared against
        backend.agent_task_lifecycle's own authoritative current_state.
        Skipped entirely when there is no observed state at all (Rule:
        "Do not invent missing state from incomplete events" carries
        forward: no observation means nothing to compare)."""
        timeline = self._timeline_service.build(task_id)
        observed_state = timeline.current_observed_state
        if observed_state is None or observed_state == task.current_state:
            return []

        responsible_event = next(
            event
            for event in reversed(events)
            if event.event_type == LIFECYCLE_TRANSITIONED
            and isinstance(event.payload, dict)
            and event.payload.get("to_state") == observed_state
        )
        return [
            AgentTaskEventConsistencyViolation(
                event_id=responsible_event.event_id,
                category=STATE_MISMATCH,
                reason=(
                    f"event-derived state {observed_state!r} conflicts with authoritative task state "
                    f"{task.current_state!r}"
                ),
            )
        ]

    def _check_relationships(self, events) -> list:
        """INVALID_RELATIONSHIP -- parent_event_id/correlation_id are
        Commit #4's own plain reference fields; resolution is scoped
        across every task (not only task_id's own events), since a parent
        legitimately may belong to a different task in one correlated
        operation (Rule: reuse Commit #4's own event structures, which
        never scoped correlation/parent references to a single task)."""
        violations = []
        all_events_by_id = {event.event_id: event for event in self._query_service.query()}

        for event in events:
            if event.parent_event_id is None:
                continue

            if event.parent_event_id == event.event_id:
                violations.append(
                    AgentTaskEventConsistencyViolation(
                        event_id=event.event_id,
                        category=INVALID_RELATIONSHIP,
                        reason="references itself as its own parent_event_id",
                    )
                )
                continue

            parent = all_events_by_id.get(event.parent_event_id)
            if parent is None:
                violations.append(
                    AgentTaskEventConsistencyViolation(
                        event_id=event.event_id,
                        category=INVALID_RELATIONSHIP,
                        reason=f"references parent_event_id {event.parent_event_id!r} which does not exist",
                    )
                )
                continue

            if parent.occurred_at > event.occurred_at:
                violations.append(
                    AgentTaskEventConsistencyViolation(
                        event_id=event.event_id,
                        category=INVALID_RELATIONSHIP,
                        reason=(
                            f"parent_event_id {event.parent_event_id!r} refers to an event that occurred "
                            "after it"
                        ),
                    )
                )

            if (
                event.correlation_id is not None
                and parent.correlation_id is not None
                and event.correlation_id != parent.correlation_id
            ):
                violations.append(
                    AgentTaskEventConsistencyViolation(
                        event_id=event.event_id,
                        category=INVALID_RELATIONSHIP,
                        reason=(
                            f"parent_event_id {event.parent_event_id!r} belongs to correlation "
                            f"{parent.correlation_id!r}, but this event belongs to {event.correlation_id!r}"
                        ),
                    )
                )

        return violations
