from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from backend.agent_learning_signals import FAILED_STRATEGY, SUCCESSFUL_STRATEGY, LLMAgentLearningSignal
from backend.agent_task_event_analytics import RECOVERY_OUTCOME_SUCCESS
from backend.agent_task_events import LLMAgentTaskEventQueryService, LLMAgentTaskEventService
from backend.llm.evaluation_scoring import MAX_SCORE, MIN_SCORE

from .policy_feedback import (
    ABANDONED,
    RECOVERED,
    FAILED as SCHEDULE_FEEDBACK_FAILED,
    LLMAgentTaskRecoveryPreflightSchedulePolicyFeedbackService,
)
from .reporting import LLMAgentTaskRecoveryPreflightScheduleReportingService

SCHEDULE_LEARNING_EVENT_TYPE = "agent_task_recovery_schedule_learning"

LEARNED = "learned"
SKIPPED_INSUFFICIENT = "insufficient_evidence"
SKIPPED_CONTRADICTORY = "contradictory_evidence"
LEARNING_OUTCOME_STATUSES = frozenset({LEARNED, SKIPPED_INSUFFICIENT, SKIPPED_CONTRADICTORY})


class InvalidAgentTaskRecoveryScheduleLearningError(ValueError):
    """Raised when learn()/get()/list() is given invalid arguments."""


def _signal_identity(signal: LLMAgentLearningSignal) -> tuple:
    """The stable content of one signal, for idempotency comparisons --
    excludes signal_id/created_at, both freshly generated on every
    construction, the same "bookkeeping is never part of the content
    comparison" discipline this whole project already establishes (see
    backend.agent_task_event_analytics.recovery_learning_integration's
    own identical helper)."""
    return (
        signal.execution_id, signal.signal_type, signal.value,
        tuple(sorted(signal.evidence.items(), key=lambda item: item[0])), signal.memory_id,
    )


@dataclass(frozen=True)
class AgentTaskRecoveryScheduleLearningOutcome:
    """learn()'s per-feedback-record verdict -- "which evidence was used"
    (Rule) for exactly one Commit #12 feedback record. `signal` is None
    whenever `status` is not LEARNED."""

    feedback_id: str
    schedule_id: str
    outcome: str
    status: str
    reason: str
    signal: Optional[LLMAgentLearningSignal]


@dataclass(frozen=True)
class AgentTaskRecoveryScheduleLearningResult:
    """learn()'s complete, durable record of one learning pass -- "what
    was learned" (Rule). `signals` is exactly the LEARNED subset of
    `outcomes`, flattened for a caller/sink that only wants the actual
    learning-signal payload."""

    task_id: str
    learning_id: str
    schedule_id: Optional[str]
    feedback_considered: int
    learned_count: int
    skipped_count: int
    outcomes: tuple
    signals: tuple
    created_at: datetime


class LLMAgentTaskRecoveryPreflightScheduleLearningService:
    """Closes this series' own scheduling loop -- schedule (#1) -> ... ->
    health (#10) -> report/history (#11) -> policy feedback (#12) -> this
    learning integration -- by converting Commit #12's own validated
    schedule feedback into backend.agent_learning_signals.
    LLMAgentLearningSignal instances, the repository's own existing,
    generic, store-agnostic learning-signal shape. Never a second
    learning engine (Rule: "Do not create another learning engine"; "no
    new ML/model-training infrastructure").

    No existing cross-domain learning APPLICATION interface was reused
    directly (inspected again for this commit, the same identity-space
    finding this whole project's own memory already documents repeatedly,
    most recently by backend.agent_task_event_analytics'
    LLMAgentTaskRecoveryLearningService for its own comparable case):
    backend.agent_memory_learning_updates.LLMAgentMemoryLearningUpdater.
    apply_signals() requires a real memory_id, backend.
    agent_strategy_learning_orchestration is bound to a plan execution's
    own execution_id, and even that ANALYTICS series' own
    LLMAgentTaskRecoveryLearningService.learn() requires an
    AgentTaskRecoveryPolicyEffectiveness built from ITS OWN decision_id-
    shaped feedback (backend.agent_task_event_analytics'
    AgentTaskRecoveryPolicyFeedback) -- a structurally different record
    from this series' own schedule_id/outcome-shaped Commit #12 feedback.
    Forcing either mapping would fabricate an identity/shape this domain
    does not have. What IS reused directly, unmodified -- exactly as that
    same analytics commit already established for its own case -- is the
    SIGNAL SHAPE itself: LLMAgentLearningSignal and its SUCCESSFUL_STRATEGY/
    FAILED_STRATEGY vocabulary, a plain value object with no schema tie to
    a specific execution store; execution_id is populated with task_id.

    Flow (Rule, followed in order): (1) load context -- Commit #11's own
    report()/history() confirm schedule_id is genuinely known before
    anything is learned from it; (2) obtain Commit #12's own already-
    persisted feedback via list() -- never re-derived; (3) evaluate
    sufficiency -- reuses the EXACT decision rule that analytics' own
    Commit #13 already established for its own RECOVERY_POLICY_FEEDBACK_
    UNKNOWN case, generalized to this domain's own outcome vocabulary:
    ABANDONED (this domain's own "unknown/no clear polarity" value) never
    produces a signal, only a SKIPPED_INSUFFICIENT outcome -- the same
    "unknown stays unknown, never guessed at" discipline; (4) evaluate
    contradiction -- a RECOVERED outcome whose OWN recorded evidence shows
    it was never dispatched at all, or that its retries were exhausted, or
    a SCHEDULE_FEEDBACK_FAILED outcome whose own evidence shows the
    eventual recovery outcome actually succeeded, is SKIPPED_CONTRADICTORY
    rather than learned from -- self-contradictory evidence produces no
    signal (Rule: "Insufficient or contradictory evidence must produce a
    non-learning result rather than guessed conclusions"), never a guess
    at which side to believe; (5) pass every remaining LEARNED signal to
    an optional `learning_sink` -- the same optional-publish extension
    point Commit #12's own policy_publisher, and analytics' own
    learning_sink, already establish for exactly this "integrate through
    an existing interface a caller separately owns" problem.

    Persistence is the same zero-new-store reuse this whole series already
    establishes: one AgentTaskRecoveryScheduleLearningResult per learn()
    call is emitted as a plain AgentTaskEvent under
    SCHEDULE_LEARNING_EVENT_TYPE -- no new store, and Commit #1's own raw
    schedule history is never touched (Rule: "Do not mutate raw schedule
    history").

    Idempotent (Rule: "Avoid duplicate learning from the same schedule/
    outcome"; "Make the operation idempotent"): before emitting anything,
    the outcomes/signals this call would produce are compared (by their
    own stable content) against task_id's most recently recorded learning
    result for the SAME schedule_id scope -- an unchanged result is
    returned as-is, and learning_sink is not re-invoked.

    Never schedules, dispatches, authorizes, or repairs anything (Rule:
    "Do not execute, reschedule, authorize, or repair recovery work") --
    every read here goes through an existing service's own already-read-
    only method; learn()'s only write is its own new event.
    """

    def __init__(
        self,
        feedback_service: LLMAgentTaskRecoveryPreflightSchedulePolicyFeedbackService = None,
        reporting_service: LLMAgentTaskRecoveryPreflightScheduleReportingService = None,
        event_service: LLMAgentTaskEventService = None,
        query_service: LLMAgentTaskEventQueryService = None,
        learning_sink=None,
    ):
        """
        Args:
            feedback_service: Defaults to a fresh Commit #12
                LLMAgentTaskRecoveryPreflightSchedulePolicyFeedbackService.
            reporting_service: Defaults to a fresh Commit #11
                LLMAgentTaskRecoveryPreflightScheduleReportingService --
                used only to confirm a given schedule_id is genuinely
                known before learning from it.
            event_service: Defaults to a fresh
                backend.agent_task_events.LLMAgentTaskEventService.
            query_service: Defaults to a fresh query service over
                event_service's own store.
            learning_sink: Optional callable, invoked with the fresh
                AgentTaskRecoveryScheduleLearningResult once per
                genuinely new result. Exceptions are caught and ignored.
        """
        self._feedback_service = (
            feedback_service
            if feedback_service is not None
            else LLMAgentTaskRecoveryPreflightSchedulePolicyFeedbackService()
        )
        self._reporting_service = (
            reporting_service if reporting_service is not None else LLMAgentTaskRecoveryPreflightScheduleReportingService()
        )
        self._event_service = event_service if event_service is not None else LLMAgentTaskEventService()
        self._query_service = (
            query_service
            if query_service is not None
            else LLMAgentTaskEventQueryService(store=self._event_service.store)
        )
        self._learning_sink = learning_sink

    def learn(self, task_id: str, schedule_id: str = None) -> AgentTaskRecoveryScheduleLearningResult:
        """Convert task_id's own currently-recorded Commit #12 feedback
        (every schedule, or exactly one when schedule_id is given) into
        learning signals. Idempotent for the same scope and evidence.

        Raises:
            InvalidAgentTaskRecoveryScheduleLearningError: If task_id is
                not a non-empty string, schedule_id is given and is not a
                non-empty string, or schedule_id is given and names no
                recorded schedule for task_id
        """
        self._require_text(task_id, "task_id")
        if schedule_id is not None:
            self._require_text(schedule_id, "schedule_id")
            history = self._reporting_service.history(task_id)
            if not any(entry.schedule_id == schedule_id for entry in history.entries):
                raise InvalidAgentTaskRecoveryScheduleLearningError(
                    f"no schedule {schedule_id!r} is recorded for task_id {task_id!r}"
                )

        records = self._feedback_service.list(task_id, schedule_id=schedule_id)

        outcomes = []
        for record in records:
            outcomes.append(self._evaluate(task_id, record))

        existing = self._find_matching(task_id, schedule_id, outcomes)
        if existing is not None:
            return existing

        signals = tuple(outcome.signal for outcome in outcomes if outcome.signal is not None)
        learned_count = len(signals)
        skipped_count = len(outcomes) - learned_count

        payload = {
            "schedule_id": schedule_id,
            "feedback_considered": len(records),
            "outcomes": [self._outcome_to_dict(o) for o in outcomes],
        }
        event = self._event_service.emit(task_id, SCHEDULE_LEARNING_EVENT_TYPE, payload=payload)
        result = self._result_from_event(event)

        self._publish(result)
        return result

    def get(self, task_id: str, learning_id: str = None) -> Optional[AgentTaskRecoveryScheduleLearningResult]:
        """task_id's learning result matching learning_id, or its most
        recently recorded one when learning_id is omitted. None when
        nothing matches.

        Raises:
            InvalidAgentTaskRecoveryScheduleLearningError: If task_id is
                not a non-empty string, or learning_id is given and is
                not a non-empty string
        """
        self._require_text(task_id, "task_id")
        if learning_id is not None:
            self._require_text(learning_id, "learning_id")

        results = self.list(task_id)
        if learning_id is not None:
            return next((r for r in results if r.learning_id == learning_id), None)
        return results[-1] if results else None

    def list(self, task_id: str) -> list:
        """Every learning result recorded for task_id, oldest to newest.

        Raises:
            InvalidAgentTaskRecoveryScheduleLearningError: If task_id is
                not a non-empty string
        """
        self._require_text(task_id, "task_id")
        events = self._query_service.query(task_id=task_id, event_types=[SCHEDULE_LEARNING_EVENT_TYPE])
        return [self._result_from_event(event) for event in events]

    def _evaluate(self, task_id: str, record) -> AgentTaskRecoveryScheduleLearningOutcome:
        if record.outcome == ABANDONED:
            return AgentTaskRecoveryScheduleLearningOutcome(
                feedback_id=record.feedback_id, schedule_id=record.schedule_id, outcome=record.outcome,
                status=SKIPPED_INSUFFICIENT, reason="abandoned outcomes carry no clear success/failure polarity",
                signal=None,
            )

        contradiction = self._contradiction_reason(record)
        if contradiction is not None:
            return AgentTaskRecoveryScheduleLearningOutcome(
                feedback_id=record.feedback_id, schedule_id=record.schedule_id, outcome=record.outcome,
                status=SKIPPED_CONTRADICTORY, reason=contradiction, signal=None,
            )

        is_recovered = record.outcome == RECOVERED
        evidence = {
            "source": "agent_task_recovery_scheduling.policy_feedback",
            "task_id": task_id,
            "schedule_id": record.schedule_id,
            "feedback_id": record.feedback_id,
            "outcome": record.outcome,
            **record.evidence,
        }
        signal = LLMAgentLearningSignal(
            execution_id=task_id,
            signal_type=SUCCESSFUL_STRATEGY if is_recovered else FAILED_STRATEGY,
            value=MAX_SCORE if is_recovered else MIN_SCORE,
            evidence=evidence,
            memory_id=None,
        )
        return AgentTaskRecoveryScheduleLearningOutcome(
            feedback_id=record.feedback_id, schedule_id=record.schedule_id, outcome=record.outcome,
            status=LEARNED, reason="evidence is sufficient and consistent with the recorded outcome", signal=signal,
        )

    @staticmethod
    def _contradiction_reason(record) -> Optional[str]:
        evidence = record.evidence
        if record.outcome == RECOVERED:
            if evidence.get("dispatched") is False:
                return "outcome claims recovery, but the schedule was never dispatched"
            if evidence.get("retry_exhausted") is True:
                return "outcome claims recovery, but retry attempts were recorded as exhausted"
        elif record.outcome == SCHEDULE_FEEDBACK_FAILED:
            if evidence.get("eventual_recovery_status") == RECOVERY_OUTCOME_SUCCESS:
                return "outcome claims failure, but the eventual recovery outcome was recorded as successful"
        return None

    def _publish(self, result: AgentTaskRecoveryScheduleLearningResult) -> None:
        if self._learning_sink is None:
            return
        try:
            self._learning_sink(result)
        except Exception:
            pass

    def _find_matching(
        self, task_id: str, schedule_id: Optional[str], outcomes: list
    ) -> Optional[AgentTaskRecoveryScheduleLearningResult]:
        candidate = tuple(
            (o.feedback_id, o.status, _signal_identity(o.signal) if o.signal is not None else None)
            for o in outcomes
        )
        for result in self.list(task_id):
            if result.schedule_id != schedule_id:
                continue
            existing = tuple(
                (o.feedback_id, o.status, _signal_identity(o.signal) if o.signal is not None else None)
                for o in result.outcomes
            )
            if existing == candidate:
                return result
        return None

    @staticmethod
    def _outcome_to_dict(outcome: AgentTaskRecoveryScheduleLearningOutcome) -> dict:
        return {
            "feedback_id": outcome.feedback_id,
            "schedule_id": outcome.schedule_id,
            "outcome": outcome.outcome,
            "status": outcome.status,
            "reason": outcome.reason,
            "signal": (
                {
                    "execution_id": outcome.signal.execution_id,
                    "signal_type": outcome.signal.signal_type,
                    "value": outcome.signal.value,
                    "evidence": outcome.signal.evidence,
                    "memory_id": outcome.signal.memory_id,
                    "signal_id": outcome.signal.signal_id,
                }
                if outcome.signal is not None
                else None
            ),
        }

    @staticmethod
    def _result_from_event(event) -> AgentTaskRecoveryScheduleLearningResult:
        payload = event.payload if isinstance(event.payload, dict) else {}
        outcomes = tuple(
            AgentTaskRecoveryScheduleLearningOutcome(
                feedback_id=entry.get("feedback_id"), schedule_id=entry.get("schedule_id"),
                outcome=entry.get("outcome"), status=entry.get("status"), reason=entry.get("reason"),
                signal=(
                    LLMAgentLearningSignal(
                        execution_id=entry["signal"].get("execution_id"),
                        signal_type=entry["signal"].get("signal_type"),
                        value=entry["signal"].get("value"),
                        evidence=entry["signal"].get("evidence") or {},
                        memory_id=entry["signal"].get("memory_id"),
                        signal_id=entry["signal"].get("signal_id"),
                        created_at=event.occurred_at,
                    )
                    if entry.get("signal") is not None
                    else None
                ),
            )
            for entry in payload.get("outcomes") or []
        )
        signals = tuple(o.signal for o in outcomes if o.signal is not None)
        return AgentTaskRecoveryScheduleLearningResult(
            task_id=event.task_id,
            learning_id=event.event_id,
            schedule_id=payload.get("schedule_id"),
            feedback_considered=payload.get("feedback_considered", 0),
            learned_count=len(signals),
            skipped_count=len(outcomes) - len(signals),
            outcomes=outcomes,
            signals=signals,
            created_at=event.occurred_at,
        )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryScheduleLearningError(
                f"{field_name} is required and must be a non-empty string"
            )
