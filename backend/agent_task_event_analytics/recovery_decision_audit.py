from typing import Optional

from backend.agent_task_events import LLMAgentTaskEventQueryService, LLMAgentTaskEventService

from .models import RECOVERY_DECISION_EVENT_TYPE, AgentTaskRecoveryDecisionAudit, AgentTaskRecoveryRecommendation

# The AgentTaskRecoveryDecisionAudit fields idempotency compares to decide
# "is this the same decision already recorded" -- decision_id/created_at are
# this record's own bookkeeping (always new on a genuine repeat), never part
# of the comparison, the same "content is stable, bookkeeping moves"
# discipline Commit #5's own record() already establishes for outcomes.
_IDENTITY_FIELDS = (
    "failure_event_id",
    "recommended_action",
    "confidence",
    "supporting_recovery_ids",
    "blocking_conditions",
    "reason",
)


class InvalidAgentTaskRecoveryDecisionAuditError(ValueError):
    """Raised when record()/get()/list() is given invalid arguments."""


class LLMAgentTaskRecoveryDecisionAuditService:
    """Persists Commit #8's own recovery recommendations so a later
    caller can see exactly what evidence a past decision was based on --
    never a generic audit framework (Rule: "Keep this task-recovery-
    specific; do not build generic auditing"; "Do not invent a generic
    audit framework"): every read and write here goes through backend.
    agent_task_events' own already-existing append-only store, via
    LLMAgentTaskEventService.emit()/LLMAgentTaskEventQueryService.query(),
    recorded under a plain new event_type
    (RECOVERY_DECISION_EVENT_TYPE) -- the exact same reuse pattern Commit
    #5 already established for recovery outcomes, applied here to
    recommendations instead.

    Audit records are append-only by construction (Rule): record() only
    ever calls emit(), itself strictly append-only, and never rewrites or
    reads back the AgentTaskRecoveryRecommendation it audits (Rule:
    "Never modify the recommendation, recovery history, or task state").

    record() is idempotent for the same decision (Rule: "Recording the
    same decision must not create accidental duplicates when an existing
    idempotency convention exists"): before emitting anything, it checks
    task_id's already-recorded audits for one whose own failure_event_id/
    recommended_action/confidence/supporting_recovery_ids/
    blocking_conditions/reason all already match -- if found, that
    existing audit is returned unchanged rather than recording a
    duplicate. This is the same content-based idempotency convention
    Commit #5's own record() already established for recovery outcomes,
    reused here rather than a new scheme.

    get()/list() are both plain reads through query() (Rule: "Retrieval
    is deterministic" -- inherited directly from that service's own
    already-deterministic ordering); get() never raises for a missing
    task_id or decision_id, returning None instead -- the same tolerant-
    read discipline every other read path in this family already
    establishes. list(limit=...) caps to the most recent entries, still
    oldest to newest -- the same convention this task family's own event
    services already use.
    """

    def __init__(
        self,
        event_service: LLMAgentTaskEventService = None,
        query_service: LLMAgentTaskEventQueryService = None,
    ):
        self._event_service = event_service if event_service is not None else LLMAgentTaskEventService()
        self._query_service = (
            query_service
            if query_service is not None
            else LLMAgentTaskEventQueryService(store=self._event_service.store)
        )

    def record(
        self, task_id: str, recommendation: AgentTaskRecoveryRecommendation
    ) -> AgentTaskRecoveryDecisionAudit:
        """Record recommendation's own evidence for task_id. Idempotent:
        an already-recorded, identical decision is returned unchanged
        rather than duplicated.

        Raises:
            InvalidAgentTaskRecoveryDecisionAuditError: If task_id is not
                a non-empty string, recommendation is not an
                AgentTaskRecoveryRecommendation, or recommendation.task_id
                does not match task_id
        """
        self._require_text(task_id)
        if not isinstance(recommendation, AgentTaskRecoveryRecommendation):
            raise InvalidAgentTaskRecoveryDecisionAuditError(
                "recommendation must be an AgentTaskRecoveryRecommendation"
            )
        if recommendation.task_id != task_id:
            raise InvalidAgentTaskRecoveryDecisionAuditError(
                f"recommendation.task_id {recommendation.task_id!r} does not match task_id {task_id!r}"
            )

        existing = self._find_matching(task_id, recommendation)
        if existing is not None:
            return existing

        payload = {
            "failure_event_id": recommendation.failure_event_id,
            "recommended_action": recommendation.recommended_action,
            "confidence": recommendation.confidence,
            "supporting_recovery_ids": list(recommendation.supporting_recovery_ids),
            "blocking_conditions": list(recommendation.blocking_conditions),
            "reason": recommendation.reason,
        }
        event = self._event_service.emit(task_id, RECOVERY_DECISION_EVENT_TYPE, payload=payload)
        return self._audit_from_event(event)

    def get(self, task_id: str, decision_id: str = None) -> Optional[AgentTaskRecoveryDecisionAudit]:
        """task_id's audit matching decision_id, or its most recently
        recorded audit when decision_id is omitted. None when nothing
        matches -- never raises for a missing task_id or decision_id.

        Raises:
            InvalidAgentTaskRecoveryDecisionAuditError: If task_id is not
                a non-empty string, or decision_id is given and is not a
                non-empty string
        """
        self._require_text(task_id)
        if decision_id is not None:
            self._require_text(decision_id, field_name="decision_id")

        audits = self.list(task_id)
        if decision_id is not None:
            return next((audit for audit in audits if audit.decision_id == decision_id), None)
        return audits[-1] if audits else None

    def list(self, task_id: str, limit: int = None) -> list:
        """Every audit recorded for task_id, oldest to newest, optionally
        capped to the most recent limit entries (still returned oldest to
        newest).

        Raises:
            InvalidAgentTaskRecoveryDecisionAuditError: If task_id is not
                a non-empty string, or limit is given and is not a
                non-negative int
        """
        self._require_text(task_id)
        if limit is not None and (not isinstance(limit, int) or isinstance(limit, bool) or limit < 0):
            raise InvalidAgentTaskRecoveryDecisionAuditError("limit must be a non-negative int when given")

        events = self._query_service.query(task_id=task_id, event_types=[RECOVERY_DECISION_EVENT_TYPE])
        audits = [self._audit_from_event(event) for event in events]
        if limit is not None:
            audits = audits[-limit:] if limit > 0 else []
        return audits

    def _find_matching(
        self, task_id: str, recommendation: AgentTaskRecoveryRecommendation
    ) -> Optional[AgentTaskRecoveryDecisionAudit]:
        for audit in self.list(task_id):
            if all(getattr(audit, field) == getattr(recommendation, field) for field in _IDENTITY_FIELDS):
                return audit
        return None

    @staticmethod
    def _audit_from_event(event) -> AgentTaskRecoveryDecisionAudit:
        payload = event.payload if isinstance(event.payload, dict) else {}
        return AgentTaskRecoveryDecisionAudit(
            decision_id=event.event_id,
            task_id=event.task_id,
            failure_event_id=payload.get("failure_event_id"),
            recommended_action=payload.get("recommended_action"),
            confidence=payload.get("confidence"),
            supporting_recovery_ids=tuple(payload.get("supporting_recovery_ids") or ()),
            blocking_conditions=tuple(payload.get("blocking_conditions") or ()),
            reason=payload.get("reason"),
            created_at=event.occurred_at,
        )

    @staticmethod
    def _require_text(value, field_name: str = "task_id") -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryDecisionAuditError(
                f"{field_name} is required and must be a non-empty string"
            )
