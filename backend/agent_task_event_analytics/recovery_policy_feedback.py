from typing import Optional

from backend.agent_task_events import LLMAgentTaskEventQueryService, LLMAgentTaskEventService

from .models import (
    RECOVERY_POLICY_FEEDBACK_EFFECTIVE,
    RECOVERY_POLICY_FEEDBACK_EVENT_TYPE,
    RECOVERY_POLICY_FEEDBACK_INEFFECTIVE,
    RECOVERY_POLICY_FEEDBACK_UNKNOWN,
    AgentTaskRecoveryDecisionComparison,
    AgentTaskRecoveryPolicyFeedback,
)

# The AgentTaskRecoveryPolicyFeedback fields idempotency compares to decide
# "is this the same decision outcome already recorded" -- feedback_id/
# created_at are this record's own bookkeeping, never part of the
# comparison, the same discipline Commits #5 and #9 already establish for
# their own content-based idempotency.
_IDENTITY_FIELDS = (
    "decision_id",
    "recovery_id",
    "recommended_action",
    "executed_action",
    "recommendation_confidence",
    "effectiveness",
    "feedback_reason",
)


class InvalidAgentTaskRecoveryPolicyFeedbackError(ValueError):
    """Raised when record()/get()/list() is given invalid arguments."""


class LLMAgentTaskRecoveryPolicyFeedbackService:
    """Feeds one Commit #10 recovery-decision comparison back into the
    recovery-policy/strategy layer as a durable, structured feedback
    record -- never a parallel learning or policy system (Rule: "Do not
    create a parallel learning or policy system"; "Do not invent a new
    learning algorithm").

    No existing cross-domain policy/strategy/memory/learning interface
    genuinely fits here (inspected before writing this service):
    backend.agent_strategy_feedback/agent_strategy_learning_integration and
    backend.agent_learning_signals/agent_memory_learning_integration are
    all scoped to a *different* identity space entirely -- an
    execution_id from backend.agent_plan_execution, or a memory_id from
    backend.agent_execution_memory -- neither of which this series' own
    task_id-scoped recovery domain has, or should invent a mapping into
    (the same "different identity space, do not force a reuse" finding
    Commit #2's own memory already documents for
    backend.agent_failure_handling.LLMAgentFailureClassification).
    backend.agent_policy_engine/agent_policy_decision/agent_policy_history
    are a separate allow/deny rule-evaluation governance system with no
    concept of a recovery recommendation at all. Reusing any of them
    directly would blur unrelated identity spaces together, not honor
    "reuse existing interfaces."

    Persistence is the same zero-new-store reuse Commits #5 and #9 already
    established: a feedback record is literally an AgentTaskEvent, emitted
    via LLMAgentTaskEventService.emit() under a plain new event_type
    (RECOVERY_POLICY_FEEDBACK_EVENT_TYPE). This *is* how this record
    becomes consumable by "future decisions" (Rule: "publish the feedback
    through existing interfaces where they support it"): get()/list() read
    it back the same deterministic way every other record in this family
    already does, ready for a later commit or caller to read -- record()
    itself never re-derives or replaces anything Commit #3/#8's own
    planner/recommender compute (Rule: "Do not directly modify policy
    weights/rules unless an existing learning interface explicitly owns
    that operation" -- no interface in this repository owns "recovery
    policy weights" at all, so none is ever touched here).

    An optional `policy_publisher` collaborator is the one genuine
    extension point for "publish through an existing interface": any
    caller who *has* wired a real policy/strategy learning integration
    (e.g. an adapter over backend.agent_strategy_learning_integration, or
    any object of their own) can supply a plain callable, invoked with the
    freshly recorded AgentTaskRecoveryPolicyFeedback exactly once per
    genuinely new record -- never for a repeat, idempotent call that
    returned an already-existing record, and never for a lookup. A
    publisher failure can never corrupt or lose the already-persisted
    feedback, or propagate out of record() (the same "a learning failure
    can never reach the real result" discipline backend.
    agent_strategy_learning_integration.on_execution_completed() already
    applies to its own orchestrator call): any exception it raises is
    caught and ignored, and record() still returns the feedback either way.

    record() is idempotent for the same decision outcome (Rule): before
    emitting anything, it checks task_id's already-recorded feedback for
    one whose own decision_id/recovery_id/recommended_action/
    executed_action/recommendation_confidence/effectiveness/feedback_reason
    all already match -- if found, that existing record is returned
    unchanged (and the publisher is not re-invoked) rather than recording
    (or re-publishing) a duplicate.

    Read-only with respect to everything but its own new event (Rule:
    "Do not execute recovery"): record() never calls anything from Commit
    #3's planner, Commit #4's executor, or any retry/readiness/context
    service -- comparison is accepted exactly as given, already fully
    computed by Commit #10.
    """

    def __init__(
        self,
        event_service: LLMAgentTaskEventService = None,
        query_service: LLMAgentTaskEventQueryService = None,
        policy_publisher=None,
    ):
        self._event_service = event_service if event_service is not None else LLMAgentTaskEventService()
        self._query_service = (
            query_service
            if query_service is not None
            else LLMAgentTaskEventQueryService(store=self._event_service.store)
        )
        self._policy_publisher = policy_publisher

    def record(
        self, task_id: str, decision_comparison: AgentTaskRecoveryDecisionComparison
    ) -> AgentTaskRecoveryPolicyFeedback:
        """Record decision_comparison's own evidence as policy feedback for
        task_id. Idempotent: an already-recorded, identical feedback record
        is returned unchanged (and the publisher, if any, is not
        re-invoked) rather than duplicated.

        Raises:
            InvalidAgentTaskRecoveryPolicyFeedbackError: If task_id is not
                a non-empty string, decision_comparison is not an
                AgentTaskRecoveryDecisionComparison, or
                decision_comparison.task_id does not match task_id
        """
        self._require_text(task_id)
        if not isinstance(decision_comparison, AgentTaskRecoveryDecisionComparison):
            raise InvalidAgentTaskRecoveryPolicyFeedbackError(
                "decision_comparison must be an AgentTaskRecoveryDecisionComparison"
            )
        if decision_comparison.task_id != task_id:
            raise InvalidAgentTaskRecoveryPolicyFeedbackError(
                f"decision_comparison.task_id {decision_comparison.task_id!r} does not match task_id {task_id!r}"
            )

        effectiveness = self._effectiveness_for(decision_comparison.was_effective)

        existing = self._find_matching(task_id, decision_comparison, effectiveness)
        if existing is not None:
            return existing

        payload = {
            "decision_id": decision_comparison.decision_id,
            "recovery_id": decision_comparison.recovery_id,
            "recommended_action": decision_comparison.recommended_action,
            "executed_action": decision_comparison.executed_action,
            "recommendation_confidence": decision_comparison.recommendation_confidence,
            "effectiveness": effectiveness,
            "feedback_reason": decision_comparison.comparison_reason,
        }
        event = self._event_service.emit(task_id, RECOVERY_POLICY_FEEDBACK_EVENT_TYPE, payload=payload)
        feedback = self._feedback_from_event(event)

        self._publish(feedback)
        return feedback

    def get(self, task_id: str, feedback_id: str = None) -> Optional[AgentTaskRecoveryPolicyFeedback]:
        """task_id's feedback matching feedback_id, or its most recently
        recorded feedback when feedback_id is omitted. None when nothing
        matches -- never raises for a missing task_id or feedback_id.

        Raises:
            InvalidAgentTaskRecoveryPolicyFeedbackError: If task_id is not
                a non-empty string, or feedback_id is given and is not a
                non-empty string
        """
        self._require_text(task_id)
        if feedback_id is not None:
            self._require_text(feedback_id, field_name="feedback_id")

        records = self.list(task_id)
        if feedback_id is not None:
            return next((record for record in records if record.feedback_id == feedback_id), None)
        return records[-1] if records else None

    def list(self, task_id: str, limit: int = None) -> list:
        """Every feedback record recorded for task_id, oldest to newest,
        optionally capped to the most recent limit entries (still returned
        oldest to newest).

        Raises:
            InvalidAgentTaskRecoveryPolicyFeedbackError: If task_id is not
                a non-empty string, or limit is given and is not a
                non-negative int
        """
        self._require_text(task_id)
        if limit is not None and (not isinstance(limit, int) or isinstance(limit, bool) or limit < 0):
            raise InvalidAgentTaskRecoveryPolicyFeedbackError("limit must be a non-negative int when given")

        events = self._query_service.query(task_id=task_id, event_types=[RECOVERY_POLICY_FEEDBACK_EVENT_TYPE])
        records = [self._feedback_from_event(event) for event in events]
        if limit is not None:
            records = records[-limit:] if limit > 0 else []
        return records

    def _publish(self, feedback: AgentTaskRecoveryPolicyFeedback) -> None:
        if self._policy_publisher is None:
            return
        try:
            self._policy_publisher(feedback)
        except Exception:
            pass

    @staticmethod
    def _effectiveness_for(was_effective: Optional[bool]) -> str:
        if was_effective is None:
            return RECOVERY_POLICY_FEEDBACK_UNKNOWN
        return RECOVERY_POLICY_FEEDBACK_EFFECTIVE if was_effective else RECOVERY_POLICY_FEEDBACK_INEFFECTIVE

    def _find_matching(
        self, task_id: str, decision_comparison: AgentTaskRecoveryDecisionComparison, effectiveness: str
    ) -> Optional[AgentTaskRecoveryPolicyFeedback]:
        candidate = {
            "decision_id": decision_comparison.decision_id,
            "recovery_id": decision_comparison.recovery_id,
            "recommended_action": decision_comparison.recommended_action,
            "executed_action": decision_comparison.executed_action,
            "recommendation_confidence": decision_comparison.recommendation_confidence,
            "effectiveness": effectiveness,
            "feedback_reason": decision_comparison.comparison_reason,
        }
        for record in self.list(task_id):
            if all(getattr(record, field) == candidate[field] for field in _IDENTITY_FIELDS):
                return record
        return None

    @staticmethod
    def _feedback_from_event(event) -> AgentTaskRecoveryPolicyFeedback:
        payload = event.payload if isinstance(event.payload, dict) else {}
        return AgentTaskRecoveryPolicyFeedback(
            task_id=event.task_id,
            feedback_id=event.event_id,
            decision_id=payload.get("decision_id"),
            recovery_id=payload.get("recovery_id"),
            recommended_action=payload.get("recommended_action"),
            executed_action=payload.get("executed_action"),
            recommendation_confidence=payload.get("recommendation_confidence"),
            effectiveness=payload.get("effectiveness"),
            feedback_reason=payload.get("feedback_reason"),
            created_at=event.occurred_at,
        )

    @staticmethod
    def _require_text(value, field_name: str = "task_id") -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryPolicyFeedbackError(
                f"{field_name} is required and must be a non-empty string"
            )
