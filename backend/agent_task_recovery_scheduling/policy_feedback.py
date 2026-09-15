from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from backend.agent_task_events import LLMAgentTaskEventQueryService, LLMAgentTaskEventService

from .dispatch import LLMAgentTaskRecoveryPreflightScheduleDispatchService
from .expiration import EXPIRED, LLMAgentTaskRecoveryPreflightScheduleExpirationService
from .service import LLMAgentTaskRecoveryPreflightSchedulingService

SCHEDULE_POLICY_FEEDBACK_EVENT_TYPE = "agent_task_recovery_schedule_policy_feedback"

RECOVERED = "recovered"
FAILED = "failed"
ABANDONED = "abandoned"
SCHEDULE_FEEDBACK_OUTCOMES = frozenset({RECOVERED, FAILED, ABANDONED})


class InvalidAgentTaskRecoveryScheduleFeedbackError(ValueError):
    """Raised when record()/get()/list() is given invalid arguments, or
    schedule_id names no recorded schedule for task_id."""


@dataclass(frozen=True)
class AgentTaskRecoveryScheduleFeedback:
    """One durable feedback record -- an AgentTaskEvent under the hood
    (Rule: "no new learning system"; zero new persistence), never a
    rewrite of the schedule/dispatch records `evidence` was read from.
    `evidence` holds only facts this repository's own state actually
    supports right now (Rule: "Only record evidence actually supported
    by repository state") -- a key is present with `None`/`False` only
    when the underlying check genuinely ran and found nothing, and
    entirely ABSENT when the corresponding optional collaborator was
    never wired at all (Rule: "Missing/partial history must be
    represented explicitly rather than guessed" -- carried over from
    Commit #10/#11's own same discipline)."""

    task_id: str
    schedule_id: str
    feedback_id: str
    outcome: str
    evidence: dict
    recorded_at: datetime


class LLMAgentTaskRecoveryPreflightSchedulePolicyFeedbackService:
    """Feeds one schedule's actual outcome back into the existing
    recovery-policy/strategy learning layer -- never a new learning
    system (Rule: "Do not create a new learning system"; "Do not invent
    a new learning algorithm").

    Inspected before writing this service, same conclusion Commit #11(-
    of-agent_task_event_analytics)'s own LLMAgentTaskRecoveryPolicyFeedbackService
    already reached for a comparable case: backend.agent_strategy_feedback/
    agent_strategy_learning_integration and backend.agent_learning_signals/
    agent_memory_learning_integration are scoped to a different identity
    space entirely (an execution_id or memory_id, never this whole
    project's own task_id), so reusing them directly would blur unrelated
    identity spaces together, not honor "reuse existing interfaces."
    backend.agent_policy_engine/agent_policy_decision are a separate
    allow/deny rule-evaluation system with no concept of a schedule
    outcome at all.

    One existing interface genuinely DOES fit, because it already shares
    this exact task_id identity space: backend.agent_task_event_analytics'
    own LLMAgentTaskRecoveryOutcomeService (Commit #4's own persisted
    SUCCESS/FAILED/PARTIAL recovery outcome) -- reused directly, when
    supplied, as this record's own "eventual recovery outcome where
    available" evidence field, never re-derived.

    Persistence is the same zero-new-store reuse Commit #11-of-
    agent_task_event_analytics already established for its own comparable
    feedback record: a feedback record is literally an AgentTaskEvent,
    emitted via the SAME backend.agent_task_events.LLMAgentTaskEventService
    every other record in this whole task_id-scoped family already uses,
    under a plain new event_type -- never a second persistence mechanism,
    and never a rewrite of Commit #1's own schedule record or Commit #3's
    own dispatch record (Rule: "Keep raw schedule history immutable").

    An optional `policy_publisher` collaborator is the one genuine
    extension point for "feed feedback through existing policy/strategy
    learning interfaces" (Rule): any caller who has wired a real
    integration (an adapter over backend.agent_strategy_learning_integration,
    or anything of their own) can supply a plain callable, invoked with
    the freshly recorded AgentTaskRecoveryScheduleFeedback exactly once
    per genuinely new record -- never for a repeat idempotent call, and
    never for a lookup. A publisher failure can never corrupt or lose the
    already-persisted feedback (Rule: "Do not change policy decisions
    synchronously as a side effect" -- a synchronous, exception-swallowing
    notification is the only side effect this class ever performs): any
    exception it raises is caught and ignored, mirroring Commit #11-of-
    agent_task_event_analytics' own identical discipline.

    record() is idempotent per (schedule_id, outcome) (Rule: "Avoid
    duplicate feedback for the same schedule/outcome"; "Make recording
    idempotent"): an already-recorded feedback for the exact same
    schedule_id and outcome is returned unchanged (and the publisher is
    not re-invoked), even if the gathered evidence would read slightly
    differently on a later call (e.g. `now` has moved on) -- outcome is
    the durable conclusion being fed back, not a live re-snapshot.

    Never schedules, dispatches, or executes recovery (Rule: "No
    scheduling or recovery execution") -- every read here goes through an
    existing service's own already-read-only query method; record()'s
    only write is its own new event.
    """

    def __init__(
        self,
        scheduling_service: LLMAgentTaskRecoveryPreflightSchedulingService = None,
        dispatch_service: LLMAgentTaskRecoveryPreflightScheduleDispatchService = None,
        event_service: LLMAgentTaskEventService = None,
        query_service: LLMAgentTaskEventQueryService = None,
        expiration_service: LLMAgentTaskRecoveryPreflightScheduleExpirationService = None,
        capacity_service=None,
        backoff_service=None,
        recovery_outcome_service=None,
        policy_publisher=None,
    ):
        """
        Args:
            scheduling_service: Defaults to a fresh
                LLMAgentTaskRecoveryPreflightSchedulingService.
            dispatch_service: Defaults to a fresh Commit #3 service built
                over scheduling_service.
            event_service: Defaults to a fresh
                backend.agent_task_events.LLMAgentTaskEventService.
            query_service: Defaults to a fresh query service over
                event_service's own store.
            expiration_service, capacity_service, backoff_service:
                Optional Commit #8/#6/#7 services -- each, when supplied,
                contributes its own evidence field; omitted entirely from
                `evidence` when not wired (never guessed).
            recovery_outcome_service: Optional backend.
                agent_task_event_analytics.LLMAgentTaskRecoveryOutcomeService
                -- when supplied and task_id has a recorded outcome, its
                status/recovery_id become this record's own "eventual
                recovery outcome where available" evidence.
            policy_publisher: Optional callable, invoked with the fresh
                AgentTaskRecoveryScheduleFeedback once per genuinely new
                record. Exceptions are caught and ignored.
        """
        self._scheduling_service = (
            scheduling_service if scheduling_service is not None else LLMAgentTaskRecoveryPreflightSchedulingService()
        )
        self._dispatch_service = (
            dispatch_service
            if dispatch_service is not None
            else LLMAgentTaskRecoveryPreflightScheduleDispatchService(scheduling_service=self._scheduling_service)
        )
        self._event_service = event_service if event_service is not None else LLMAgentTaskEventService()
        self._query_service = (
            query_service
            if query_service is not None
            else LLMAgentTaskEventQueryService(store=self._event_service.store)
        )
        self._expiration_service = expiration_service
        self._capacity_service = capacity_service
        self._backoff_service = backoff_service
        self._recovery_outcome_service = recovery_outcome_service
        self._policy_publisher = policy_publisher

    def record(
        self, task_id: str, schedule_id: str, outcome: str, now: Optional[datetime] = None
    ) -> AgentTaskRecoveryScheduleFeedback:
        """Record schedule_id's actual outcome for task_id, with evidence
        gathered from every existing service currently wired. Idempotent
        per (schedule_id, outcome).

        Raises:
            InvalidAgentTaskRecoveryScheduleFeedbackError: If task_id/
                schedule_id is not a non-empty string, outcome is not one
                of RECOVERED/FAILED/ABANDONED, now is given and is not a
                datetime, or schedule_id names no recorded schedule for
                task_id
        """
        self._require_text(task_id, "task_id")
        self._require_text(schedule_id, "schedule_id")
        if outcome not in SCHEDULE_FEEDBACK_OUTCOMES:
            raise InvalidAgentTaskRecoveryScheduleFeedbackError(
                f"outcome must be one of {sorted(SCHEDULE_FEEDBACK_OUTCOMES)}, got {outcome!r}"
            )
        now = self._resolve_now(now)

        schedule = self._scheduling_service.get(task_id, schedule_id)
        if schedule is None:
            raise InvalidAgentTaskRecoveryScheduleFeedbackError(
                f"no schedule {schedule_id!r} is recorded for task_id {task_id!r}"
            )

        existing = self._find_matching(task_id, schedule_id, outcome)
        if existing is not None:
            return existing

        evidence = self._gather_evidence(task_id, schedule, now)
        payload = {"schedule_id": schedule_id, "outcome": outcome, "evidence": evidence}
        event = self._event_service.emit(task_id, SCHEDULE_POLICY_FEEDBACK_EVENT_TYPE, payload=payload)
        feedback = self._feedback_from_event(event)

        self._publish(feedback)
        return feedback

    def get(self, task_id: str, feedback_id: str = None) -> Optional[AgentTaskRecoveryScheduleFeedback]:
        """task_id's feedback matching feedback_id, or its most recently
        recorded feedback when feedback_id is omitted. None when nothing
        matches.

        Raises:
            InvalidAgentTaskRecoveryScheduleFeedbackError: If task_id is
                not a non-empty string, or feedback_id is given and is
                not a non-empty string
        """
        self._require_text(task_id, "task_id")
        if feedback_id is not None:
            self._require_text(feedback_id, "feedback_id")

        records = self.list(task_id)
        if feedback_id is not None:
            return next((r for r in records if r.feedback_id == feedback_id), None)
        return records[-1] if records else None

    def list(self, task_id: str, schedule_id: str = None) -> list:
        """Every feedback record recorded for task_id, oldest to newest,
        optionally filtered to one schedule_id.

        Raises:
            InvalidAgentTaskRecoveryScheduleFeedbackError: If task_id is
                not a non-empty string, or schedule_id is given and is
                not a non-empty string
        """
        self._require_text(task_id, "task_id")
        if schedule_id is not None:
            self._require_text(schedule_id, "schedule_id")

        events = self._query_service.query(task_id=task_id, event_types=[SCHEDULE_POLICY_FEEDBACK_EVENT_TYPE])
        records = [self._feedback_from_event(event) for event in events]
        if schedule_id is not None:
            records = [r for r in records if r.schedule_id == schedule_id]
        return records

    def _gather_evidence(self, task_id: str, schedule, now: datetime) -> dict:
        evidence: dict = {
            "scheduling_status": schedule.status,
            "cancellation_reason": schedule.cancellation_reason,
        }

        dispatches = [d for d in self._dispatch_service.list(task_id) if d.schedule_id == schedule.schedule_id]
        dispatch = dispatches[0] if dispatches else None
        evidence["dispatched"] = dispatch is not None
        if dispatch is not None:
            evidence["dispatch_status"] = dispatch.status
            evidence["queue_reference"] = dispatch.queue_reference
            evidence["time_to_dispatch_seconds"] = (dispatch.dispatched_at - schedule.created_at).total_seconds()

        if self._expiration_service is not None:
            expiration = self._expiration_service.check(task_id, schedule.schedule_id, now=now)
            evidence["expired"] = expiration.state == EXPIRED

        if self._backoff_service is not None:
            backoff = self._backoff_service.calculate(task_id, schedule.schedule_id, now=now)
            evidence["retry_attempt"] = backoff.attempt
            evidence["retry_exhausted"] = backoff.dead_letter_required

        if self._capacity_service is not None:
            capacity = self._capacity_service.check(task_id, schedule.schedule_id)
            evidence["capacity_blocking_reasons"] = list(capacity.blocking_reasons)

        if self._recovery_outcome_service is not None:
            recovery_outcome = self._recovery_outcome_service.get(task_id)
            if recovery_outcome is not None:
                evidence["eventual_recovery_status"] = recovery_outcome.status
                evidence["eventual_recovery_id"] = recovery_outcome.recovery_id

        return evidence

    def _find_matching(self, task_id: str, schedule_id: str, outcome: str) -> Optional[AgentTaskRecoveryScheduleFeedback]:
        for record in self.list(task_id, schedule_id=schedule_id):
            if record.outcome == outcome:
                return record
        return None

    def _publish(self, feedback: AgentTaskRecoveryScheduleFeedback) -> None:
        if self._policy_publisher is None:
            return
        try:
            self._policy_publisher(feedback)
        except Exception:
            pass

    @staticmethod
    def _feedback_from_event(event) -> AgentTaskRecoveryScheduleFeedback:
        payload = event.payload if isinstance(event.payload, dict) else {}
        return AgentTaskRecoveryScheduleFeedback(
            task_id=event.task_id,
            schedule_id=payload.get("schedule_id"),
            feedback_id=event.event_id,
            outcome=payload.get("outcome"),
            evidence=payload.get("evidence") or {},
            recorded_at=event.occurred_at,
        )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryScheduleFeedbackError(
                f"{field_name} is required and must be a non-empty string"
            )

    @staticmethod
    def _resolve_now(now) -> datetime:
        if now is None:
            return datetime.now(timezone.utc)
        if not isinstance(now, datetime):
            raise InvalidAgentTaskRecoveryScheduleFeedbackError("now must be a datetime when given")
        return now
