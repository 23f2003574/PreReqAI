from typing import Optional

from backend.agent_learning_signals import FAILED_STRATEGY, SUCCESSFUL_STRATEGY, LLMAgentLearningSignal
from backend.agent_task_events import LLMAgentTaskEventQueryService, LLMAgentTaskEventService
from backend.llm.evaluation_scoring import MAX_SCORE, MIN_SCORE

from .models import (
    RECOVERY_LEARNING_EVENT_TYPE,
    RECOVERY_POLICY_FEEDBACK_EFFECTIVE,
    RECOVERY_POLICY_FEEDBACK_UNKNOWN,
    AgentTaskRecoveryLearningResult,
    AgentTaskRecoveryPolicyEffectiveness,
)
from .recovery_policy_feedback import LLMAgentTaskRecoveryPolicyFeedbackService, latest_feedback_per_decision


class InvalidAgentTaskRecoveryLearningError(ValueError):
    """Raised when learn()/get()/list() is given invalid arguments."""


def _signal_identity(signal: LLMAgentLearningSignal) -> tuple:
    """The stable content of one signal, for idempotency/equality
    comparisons -- excludes signal_id/created_at, both freshly generated
    on every construction (LLMAgentLearningSignal's own field defaults),
    the same "bookkeeping is never part of the content comparison"
    discipline Commits #5/#9/#11 already establish for their own records."""
    return (
        signal.execution_id,
        signal.signal_type,
        signal.value,
        tuple(sorted(signal.evidence.items(), key=lambda item: item[0])),
        signal.memory_id,
    )


class LLMAgentTaskRecoveryLearningService:
    """Converts Commit #12's own validated recovery-policy effectiveness
    into backend.agent_learning_signals.LLMAgentLearningSignal instances
    -- the repository's own existing, generic learning-signal shape --
    closing this series' full loop: recommendation (#8) -> decision (#9)
    -> execution (#4/#5) -> comparison (#10) -> policy feedback (#11) ->
    effectiveness (#12) -> this learning integration.

    No existing cross-domain learning APPLICATION interface was reused
    directly (inspected again for this commit, the same identity-space
    finding Commits #11/#12's own memory already document twice):
    backend.agent_memory_learning_updates.LLMAgentMemoryLearningUpdater.
    apply_signals() requires a real Commit #1 memory_id
    (memory_service.get(memory_id) raises if it does not exist), and
    backend.agent_strategy_learning_orchestration is bound to
    backend.agent_plan_execution's own execution_id -- neither concept
    exists in this series' own task_id-scoped recovery domain. What IS
    reused directly, unmodified, is the SIGNAL SHAPE itself --
    LLMAgentLearningSignal and its SUCCESSFUL_STRATEGY/FAILED_STRATEGY
    vocabulary -- since that dataclass is a plain, store-agnostic value
    object with no schema tie to a specific execution store (Rule:
    "Find the existing Agent Memory / Strategy Learning / Policy Feedback
    integration points. Reuse those real interfaces."): execution_id is
    populated with task_id here, the same "label naming which thing this
    signal is about" role it already plays for a plan execution, just
    naming a different (but structurally compatible) kind of subject.

    Only evidence-backed outcomes ever produce a signal (Rule: "Only learn
    from explicit/evidence-backed outcomes"; "Unknown outcomes must
    produce no positive/negative learning signal"): a decision whose
    Commit #11 feedback.effectiveness is RECOVERY_POLICY_FEEDBACK_UNKNOWN
    contributes nothing to `signals` at all -- not a neutral-value signal,
    no signal whatsoever -- counted instead in skipped_unknown_count, the
    same "unknown stays unknown, never guessed at" discipline this entire
    series already applies everywhere else.

    Reuses Commit #11's own feedback records directly for per-decision
    provenance (decision_id/recovery_id/recommended_action/executed_action/
    recommendation_confidence), and Commit #12's own already-computed
    `effectiveness` only for aggregate context (effectiveness_rate, and a
    policy/strategy reference via effectiveness_by_policy's own category
    key, when Commit #12 was run with a classifier) -- never re-deriving
    either a second way. A decision recorded more than once by Commit #11
    is deduplicated to its most recently recorded feedback first (the
    same latest_feedback_per_decision() Commit #12 already uses), so a
    superseded evaluation is never learned from twice.

    Persistence is the same zero-new-store reuse Commits #5/#9/#11 already
    establish (Rule: "Do not invent a new learning store or learning
    algorithm" -- the underlying append-only event log is not new, only a
    plain new event_type tag is): one AgentTaskRecoveryLearningResult per
    learn() call is emitted as an AgentTaskEvent under
    RECOVERY_LEARNING_EVENT_TYPE. record() is idempotent for the same
    decision/outcome (Rule): before emitting anything, the signals this
    call would produce are compared (by their own stable content, ignoring
    each signal's freshly-generated signal_id/created_at) against
    task_id's most recently recorded learning result -- an unchanged
    result is returned as-is rather than duplicated, and the optional
    learning_sink below is not re-invoked.

    An optional `learning_sink` collaborator is the one genuine extension
    point for "integrate through the repository's existing learning
    interfaces so future strategy/policy selection can consume the
    signal" (Rule) -- the same optional-publish pattern Commit #11's own
    policy_publisher already establishes for exactly this problem: a
    caller who separately knows a real memory_id or execution_id these
    signals should be folded into (via their own
    LLMAgentMemoryLearningUpdater.apply_signals() or equivalent) supplies
    a plain callable, invoked with the newly recorded
    AgentTaskRecoveryLearningResult exactly once per genuinely new
    result -- never for an idempotent repeat. A sink's own exception is
    caught and ignored (Commit #11's own "a learning failure can never
    reach the real result" discipline), and never blocks the already-
    persisted result from being returned.

    Read-only with respect to everything else (Rule: "Keep authoritative
    task state untouched"; "Do not directly mutate strategy/policy rules
    unless an existing learning API owns that mutation"): learn() never
    calls plan()/execute()/record() on anything but its own new event, and
    never touches Commit #3/#8's own planner/recommender logic at all.
    """

    def __init__(
        self,
        event_service: LLMAgentTaskEventService = None,
        query_service: LLMAgentTaskEventQueryService = None,
        feedback_service: LLMAgentTaskRecoveryPolicyFeedbackService = None,
        learning_sink=None,
    ):
        self._event_service = event_service if event_service is not None else LLMAgentTaskEventService()
        self._query_service = (
            query_service
            if query_service is not None
            else LLMAgentTaskEventQueryService(store=self._event_service.store)
        )
        self._feedback_service = (
            feedback_service if feedback_service is not None else LLMAgentTaskRecoveryPolicyFeedbackService()
        )
        self._learning_sink = learning_sink

    def learn(
        self, task_id: str, effectiveness: AgentTaskRecoveryPolicyEffectiveness
    ) -> AgentTaskRecoveryLearningResult:
        """Convert task_id's own Commit #11 feedback into learning signals,
        using `effectiveness` (Commit #12's own analyze(task_id) result)
        for aggregate context. Idempotent: an already-recorded, identical
        result is returned unchanged (and learning_sink, if any, is not
        re-invoked) rather than duplicated.

        Raises:
            InvalidAgentTaskRecoveryLearningError: If task_id is not a
                non-empty string, effectiveness is not an
                AgentTaskRecoveryPolicyEffectiveness, or
                effectiveness.task_id does not match task_id
        """
        self._require_text(task_id)
        if not isinstance(effectiveness, AgentTaskRecoveryPolicyEffectiveness):
            raise InvalidAgentTaskRecoveryLearningError(
                "effectiveness must be an AgentTaskRecoveryPolicyEffectiveness"
            )
        if effectiveness.task_id != task_id:
            raise InvalidAgentTaskRecoveryLearningError(
                f"effectiveness.task_id {effectiveness.task_id!r} does not match task_id {task_id!r}"
            )

        records = latest_feedback_per_decision(self._feedback_service.list(task_id))
        policy_reference = next(iter(effectiveness.effectiveness_by_policy), None)

        signals = []
        skipped_unknown_count = 0
        for record in records:
            if record.effectiveness == RECOVERY_POLICY_FEEDBACK_UNKNOWN:
                skipped_unknown_count += 1
                continue
            signals.append(self._signal_for(task_id, record, effectiveness, policy_reference))

        existing = self._find_matching(task_id, signals, skipped_unknown_count, len(records))
        if existing is not None:
            return existing

        payload = {
            "decisions_considered": len(records),
            "skipped_unknown_count": skipped_unknown_count,
            "signals": [self._signal_to_dict(signal) for signal in signals],
        }
        event = self._event_service.emit(task_id, RECOVERY_LEARNING_EVENT_TYPE, payload=payload)
        result = self._result_from_event(event)

        self._publish(result)
        return result

    def get(self, task_id: str, learning_id: str = None) -> Optional[AgentTaskRecoveryLearningResult]:
        """task_id's learning result matching learning_id, or its most
        recently recorded one when learning_id is omitted. None when
        nothing matches -- never raises for a missing task_id or
        learning_id.

        Raises:
            InvalidAgentTaskRecoveryLearningError: If task_id is not a
                non-empty string, or learning_id is given and is not a
                non-empty string
        """
        self._require_text(task_id)
        if learning_id is not None:
            self._require_text(learning_id, field_name="learning_id")

        results = self.list(task_id)
        if learning_id is not None:
            return next((result for result in results if result.learning_id == learning_id), None)
        return results[-1] if results else None

    def list(self, task_id: str, limit: int = None) -> list:
        """Every learning result recorded for task_id, oldest to newest,
        optionally capped to the most recent limit entries (still returned
        oldest to newest).

        Raises:
            InvalidAgentTaskRecoveryLearningError: If task_id is not a
                non-empty string, or limit is given and is not a
                non-negative int
        """
        self._require_text(task_id)
        if limit is not None and (not isinstance(limit, int) or isinstance(limit, bool) or limit < 0):
            raise InvalidAgentTaskRecoveryLearningError("limit must be a non-negative int when given")

        events = self._query_service.query(task_id=task_id, event_types=[RECOVERY_LEARNING_EVENT_TYPE])
        results = [self._result_from_event(event) for event in events]
        if limit is not None:
            results = results[-limit:] if limit > 0 else []
        return results

    @staticmethod
    def _signal_for(task_id: str, record, effectiveness, policy_reference) -> LLMAgentLearningSignal:
        is_effective = record.effectiveness == RECOVERY_POLICY_FEEDBACK_EFFECTIVE
        evidence = {
            "source": "recovery_policy_feedback",
            "task_id": task_id,
            "decision_id": record.decision_id,
            "recovery_id": record.recovery_id,
            "recommended_action": record.recommended_action,
            "executed_action": record.executed_action,
            "recommendation_confidence": record.recommendation_confidence,
            "effectiveness_rate": effectiveness.effectiveness_rate,
            "feedback_id": record.feedback_id,
        }
        if policy_reference is not None:
            evidence["policy_reference"] = policy_reference

        return LLMAgentLearningSignal(
            execution_id=task_id,
            signal_type=SUCCESSFUL_STRATEGY if is_effective else FAILED_STRATEGY,
            value=MAX_SCORE if is_effective else MIN_SCORE,
            evidence=evidence,
            memory_id=None,
        )

    def _publish(self, result: AgentTaskRecoveryLearningResult) -> None:
        if self._learning_sink is None:
            return
        try:
            self._learning_sink(result)
        except Exception:
            pass

    def _find_matching(
        self, task_id: str, signals: list, skipped_unknown_count: int, decisions_considered: int
    ) -> Optional[AgentTaskRecoveryLearningResult]:
        candidate_identity = tuple(_signal_identity(signal) for signal in signals)
        for result in self.list(task_id):
            if (
                result.decisions_considered == decisions_considered
                and result.skipped_unknown_count == skipped_unknown_count
                and tuple(_signal_identity(signal) for signal in result.signals) == candidate_identity
            ):
                return result
        return None

    @staticmethod
    def _signal_to_dict(signal: LLMAgentLearningSignal) -> dict:
        return {
            "execution_id": signal.execution_id,
            "signal_type": signal.signal_type,
            "value": signal.value,
            "evidence": signal.evidence,
            "memory_id": signal.memory_id,
            "signal_id": signal.signal_id,
        }

    @staticmethod
    def _result_from_event(event) -> AgentTaskRecoveryLearningResult:
        payload = event.payload if isinstance(event.payload, dict) else {}
        signals = tuple(
            LLMAgentLearningSignal(
                execution_id=entry.get("execution_id"),
                signal_type=entry.get("signal_type"),
                value=entry.get("value"),
                evidence=entry.get("evidence") or {},
                memory_id=entry.get("memory_id"),
                signal_id=entry.get("signal_id"),
                created_at=event.occurred_at,
            )
            for entry in payload.get("signals") or []
        )
        return AgentTaskRecoveryLearningResult(
            task_id=event.task_id,
            learning_id=event.event_id,
            decisions_considered=payload.get("decisions_considered", 0),
            skipped_unknown_count=payload.get("skipped_unknown_count", 0),
            signals=signals,
            created_at=event.occurred_at,
        )

    @staticmethod
    def _require_text(value, field_name: str = "task_id") -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryLearningError(f"{field_name} is required and must be a non-empty string")
