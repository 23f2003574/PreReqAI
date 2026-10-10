from collections import Counter
from datetime import datetime

from backend.agent_task_events import (
    CONTEXT_UPDATED,
    DEPENDENCY_REMOVED,
    LIFECYCLE_TRANSITIONED,
    READINESS_CHANGED,
    RETRY_SCHEDULED,
    LLMAgentTaskEventQueryService,
    LLMAgentTaskEventReplayService,
    LLMAgentTaskEventTimelineService,
)
from backend.agent_task_lifecycle import CANCELLED, FAILED

from .models import (
    FAILURE_CATEGORY_CONTEXT,
    FAILURE_CATEGORY_DEPENDENCY,
    FAILURE_CATEGORY_EXECUTION,
    FAILURE_CATEGORY_RETRY_EXHAUSTION,
    FAILURE_CATEGORY_TIMEOUT_CANCELLATION,
    FAILURE_CATEGORY_UNKNOWN,
    FAILURE_CATEGORY_VALIDATION_POLICY,
    AgentTaskEventFailure,
    AgentTaskEventFailureAnalysis,
)

_TERMINAL_FAILURE_STATES = (FAILED, CANCELLED)


class InvalidAgentTaskEventFailureClassificationError(ValueError):
    """Raised when classify() is given invalid arguments."""


class LLMAgentTaskEventFailureClassifier:
    """Turns raw task-event failures into structured, actionable
    categories -- explicitly kept separate from Commit #1's own
    LLMAgentTaskEventAnalyticsService (Rule: "Keep this separate from
    analytics: analytics measures failures; this commit explains/
    classifies them"): analyze() answers "how many, how long, what
    outcome"; classify() answers "why, for each one, in this task's own
    event-stream terms."

    Does not invent a second error taxonomy (Rule): backend.
    agent_failure_handling.LLMAgentFailureClassification already owns
    "why is this plan step failing," scoped to (execution_id, step_id) --
    a different identity space from this classifier's own task_id scope,
    so it is not reused directly (see FAILURE_CATEGORIES's own docstring
    for the one place the two deliberately echo each other in naming).
    This classifier's own categories are each backed by an existing
    backend.agent_task_events event type or backend.agent_task_lifecycle
    state -- never a new event type invented to support a category (Rule:
    "Do not invent event types that aren't in the repository").

    Composes exactly the same two collaborators Commit #1's own
    LLMAgentTaskEventAnalyticsService does (Rule: "Reuse existing event
    querying"): backend.agent_task_events.LLMAgentTaskEventTimelineService
    for the ordered raw event list, and LLMAgentTaskEventReplayService for
    the one authoritative, validated final_state/state_transitions answer
    terminal_failure is built from. Read-only: classify() never calls
    emit()/save()/delete() anywhere, and never mutates the events it
    reads (Rule: "Never rewrite the original event/error" -- every
    AgentTaskEventFailure only ever references its own source event_id/
    occurred_at, never a copy of the event object itself).

    Classification precedence, applied per candidate failure event (a raw
    LIFECYCLE_TRANSITIONED event whose payload["to_state"] is exactly
    FAILED or CANCELLED -- an absent or unrecognized to_state is never a
    candidate at all, the same "absent optional metadata is not a
    violation" discipline this whole event family already establishes):
      1. to_state == CANCELLED -> FAILURE_CATEGORY_TIMEOUT_CANCELLATION,
         always (direct, unambiguous mapping from the lifecycle state
         itself).
      2. Any RETRY_SCHEDULED event recorded anywhere earlier in the
         stream -> FAILURE_CATEGORY_RETRY_EXHAUSTION (a task that was
         retried at least once and still ended up here has exhausted
         those attempts, regardless of what immediately preceded it).
      3. The immediately preceding event (any type, chronologically) is
         DEPENDENCY_REMOVED / READINESS_CHANGED / CONTEXT_UPDATED ->
         FAILURE_CATEGORY_DEPENDENCY / FAILURE_CATEGORY_VALIDATION_POLICY
         (backend.agent_task_readiness's own gate already folds a policy
         check into readiness, so a readiness change immediately before a
         failure is this classifier's own clean signal for "validation/
         policy," rather than inventing a dedicated policy event type) /
         FAILURE_CATEGORY_CONTEXT, respectively.
      4. No preceding event exists at all (Rule: "Unknown failures must
         remain explicitly unknown" -- there is no information to base
         any category on) -> FAILURE_CATEGORY_UNKNOWN.
      5. Otherwise -> FAILURE_CATEGORY_EXECUTION, the default reading of
         an ordinary failure with no other distinguishing signal nearby.

    Deterministic (Rule): both collaborators are already deterministic
    over a fixed event stream, classification is a pure function of their
    outputs plus simple positional lookups, and dict/Counter iteration
    order is itself deterministic given a fixed, already-chronologically-
    ordered input.
    """

    def __init__(
        self,
        query_service: LLMAgentTaskEventQueryService = None,
        timeline_service: LLMAgentTaskEventTimelineService = None,
        replay_service: LLMAgentTaskEventReplayService = None,
    ):
        self._query_service = query_service if query_service is not None else LLMAgentTaskEventQueryService()
        self._timeline_service = (
            timeline_service
            if timeline_service is not None
            else LLMAgentTaskEventTimelineService(self._query_service)
        )
        self._replay_service = (
            replay_service if replay_service is not None else LLMAgentTaskEventReplayService(self._query_service)
        )

    def classify(
        self, task_id: str, start_time: datetime = None, end_time: datetime = None
    ) -> AgentTaskEventFailureAnalysis:
        """Classify task_id's raw failure-claiming events (optionally
        narrowed to [start_time, end_time]) into structured categories.

        Never raises for a task_id with no recorded events, or none that
        qualify as failures: an empty, fully-populated result (this
        service holds no opinion on task identity, the same discipline
        every other read path in this family already establishes).

        Raises:
            InvalidAgentTaskEventFailureClassificationError: If task_id
                is not a non-empty string
            InvalidAgentTaskEventQueryError: If start_time/end_time is
                given and is not a datetime (Commit #2-of-the-agent-task-
                events-series' own query()/error, propagated unchanged)
        """
        if not task_id or not isinstance(task_id, str):
            raise InvalidAgentTaskEventFailureClassificationError(
                "task_id is required and must be a non-empty string"
            )

        timeline = self._timeline_service.build(task_id, start_time=start_time, end_time=end_time)
        replay_result = self._replay_service.replay(task_id, start_time=start_time, end_time=end_time)

        events = timeline.events
        failures = []
        for index, event in enumerate(events):
            if event.event_type != LIFECYCLE_TRANSITIONED:
                continue
            to_state = event.payload.get("to_state") if isinstance(event.payload, dict) else None
            if to_state not in _TERMINAL_FAILURE_STATES:
                continue
            category, reason = self._classify_event(events, index, to_state)
            failures.append(
                AgentTaskEventFailure(
                    event_id=event.event_id,
                    occurred_at=event.occurred_at,
                    to_state=to_state,
                    category=category,
                    reason=reason,
                )
            )

        category_counts = dict(Counter(failure.category for failure in failures))

        terminal_failure = None
        if replay_result.final_state in _TERMINAL_FAILURE_STATES and replay_result.state_transitions:
            terminal_event_id = replay_result.state_transitions[-1].event_id
            terminal_failure = next((f for f in failures if f.event_id == terminal_event_id), None)

        return AgentTaskEventFailureAnalysis(
            task_id=task_id,
            start_time=start_time,
            end_time=end_time,
            failure_count=len(failures),
            failures=tuple(failures),
            category_counts=category_counts,
            terminal_failure=terminal_failure,
        )

    @staticmethod
    def _classify_event(events, index: int, to_state: str):
        if to_state == CANCELLED:
            return FAILURE_CATEGORY_TIMEOUT_CANCELLATION, "task was cancelled"

        retry_count = sum(1 for event in events[:index] if event.event_type == RETRY_SCHEDULED)
        if retry_count > 0:
            return (
                FAILURE_CATEGORY_RETRY_EXHAUSTION,
                f"task failed after {retry_count} retry attempt(s) were scheduled",
            )

        preceding = events[index - 1] if index > 0 else None
        if preceding is None:
            return FAILURE_CATEGORY_UNKNOWN, "no preceding event is available to explain this failure"

        if preceding.event_type == DEPENDENCY_REMOVED:
            return FAILURE_CATEGORY_DEPENDENCY, "task failed immediately after a dependency was removed"
        if preceding.event_type == READINESS_CHANGED:
            return (
                FAILURE_CATEGORY_VALIDATION_POLICY,
                "task failed immediately after a readiness/policy check changed",
            )
        if preceding.event_type == CONTEXT_UPDATED:
            return FAILURE_CATEGORY_CONTEXT, "task failed immediately after its context was updated"

        return FAILURE_CATEGORY_EXECUTION, "task failed during execution with no other distinguishing signal"
