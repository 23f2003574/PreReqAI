from datetime import datetime, timezone
from typing import Optional

from backend.agent_task_events import LLMAgentTaskEventQueryService, LLMAgentTaskEventService

from .models import (
    RECOVERY_OUTCOME_EVENT_TYPE,
    RECOVERY_OUTCOME_FAILED,
    RECOVERY_OUTCOME_PARTIAL,
    RECOVERY_OUTCOME_SUCCESS,
    AgentTaskFailureRecoveryResult,
    AgentTaskRecoveryOutcome,
)


class InvalidAgentTaskRecoveryOutcomeError(ValueError):
    """Raised when record()/get()/list() is given invalid arguments."""


class LLMAgentTaskRecoveryOutcomeService:
    """Persists the outcome of a Commit #4 recovery attempt so later task
    logic can tell successful, failed, and partially completed recovery
    apart -- never a new audit/history store (Rule): every read and write
    here goes through backend.agent_task_events' own already-existing
    append-only store, via Commit #1-of-that-series' own
    LLMAgentTaskEventService.emit() and Commit #2's own
    LLMAgentTaskEventQueryService.query(), recorded under a plain new
    event_type (RECOVERY_OUTCOME_EVENT_TYPE) rather than a second
    persistence mechanism entirely.

    Not backend.agent_task_state_history (Rule: "Do not duplicate task
    state history"): that module's own append-only trail is scoped to
    Commit #1-of-the-lifecycle-series' own AgentTask.current_state
    transitions -- a different concept from "did a recovery attempt for
    this failure succeed," which has no lifecycle-state shape at all.

    Never touches backend.agent_task_lifecycle (Rule: "Do not turn
    outcomes into authoritative task state") and never rewrites the
    original failure event this outcome concerns (Rule: "Preserve the
    original event unchanged") -- record() only ever calls emit(), which
    is itself strictly append-only; the failure event named by
    source_failure_event_id is never read back, modified, or even looked
    up by this service at all.

    record() is idempotent for the same recovery operation (Rule): before
    emitting anything, it checks task_id's already-recorded outcomes for
    one whose own source_failure_event_id/planned_action/executed_action/
    status/reason all already match -- if found, that existing outcome is
    returned unchanged rather than recording a duplicate. This is a
    content-based check, not a caller-supplied idempotency key, since
    Commit #4's own AgentTaskFailureRecoveryResult carries no operation id
    of its own to key on.

    get()/list() are both plain reads through query() (Rule: "Retrieval
    must be deterministic" -- inherited directly from that service's own
    already-deterministic ordering); get() never raises for a missing
    task_id or recovery_id, returning None instead -- the same tolerant-
    read discipline every other read path in this family already
    establishes.
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

    def record(self, task_id: str, recovery_result: AgentTaskFailureRecoveryResult) -> AgentTaskRecoveryOutcome:
        """Record recovery_result's outcome for task_id. Idempotent: an
        already-recorded, identical outcome is returned unchanged rather
        than duplicated.

        Raises:
            InvalidAgentTaskRecoveryOutcomeError: If task_id is not a
                non-empty string, recovery_result is not an
                AgentTaskFailureRecoveryResult, or recovery_result.task_id
                does not match task_id
        """
        self._require_text(task_id)
        if not isinstance(recovery_result, AgentTaskFailureRecoveryResult):
            raise InvalidAgentTaskRecoveryOutcomeError(
                "recovery_result must be an AgentTaskFailureRecoveryResult"
            )
        if recovery_result.task_id != task_id:
            raise InvalidAgentTaskRecoveryOutcomeError(
                f"recovery_result.task_id {recovery_result.task_id!r} does not match task_id {task_id!r}"
            )

        status = self._status_for(recovery_result)
        reason = recovery_result.failure_reason if recovery_result.failure_reason is not None else (
            recovery_result.affected_reference
        )

        existing = self._find_matching(
            task_id,
            source_failure_event_id=recovery_result.source_failure_event_id,
            planned_action=recovery_result.planned_action,
            executed_action=recovery_result.executed_action,
            status=status,
            reason=reason,
        )
        if existing is not None:
            return existing

        now = datetime.now(timezone.utc).isoformat()
        payload = {
            "source_failure_event_id": recovery_result.source_failure_event_id,
            "planned_action": recovery_result.planned_action,
            "executed_action": recovery_result.executed_action,
            "status": status,
            "reason": reason,
            "started_at": now,
            "completed_at": now,
        }
        event = self._event_service.emit(task_id, RECOVERY_OUTCOME_EVENT_TYPE, payload=payload)
        return self._outcome_from_event(event)

    def get(self, task_id: str, recovery_id: str = None) -> Optional[AgentTaskRecoveryOutcome]:
        """task_id's outcome matching recovery_id, or its most recently
        recorded outcome when recovery_id is omitted. None when nothing
        matches -- never raises for a missing task_id or recovery_id.

        Raises:
            InvalidAgentTaskRecoveryOutcomeError: If task_id is not a
                non-empty string, or recovery_id is given and is not a
                non-empty string
        """
        self._require_text(task_id)
        if recovery_id is not None:
            self._require_text(recovery_id, field_name="recovery_id")

        outcomes = self.list(task_id)
        if recovery_id is not None:
            return next((outcome for outcome in outcomes if outcome.recovery_id == recovery_id), None)
        return outcomes[-1] if outcomes else None

    def list(self, task_id: str) -> list:
        """Every outcome recorded for task_id, oldest to newest.

        Raises:
            InvalidAgentTaskRecoveryOutcomeError: If task_id is not a
                non-empty string
        """
        self._require_text(task_id)
        events = self._query_service.query(task_id=task_id, event_types=[RECOVERY_OUTCOME_EVENT_TYPE])
        return [self._outcome_from_event(event) for event in events]

    def _find_matching(self, task_id: str, **fields) -> Optional[AgentTaskRecoveryOutcome]:
        for outcome in self.list(task_id):
            if all(getattr(outcome, name) == value for name, value in fields.items()):
                return outcome
        return None

    @staticmethod
    def _status_for(recovery_result: AgentTaskFailureRecoveryResult) -> str:
        if not recovery_result.success:
            return RECOVERY_OUTCOME_FAILED
        if recovery_result.partial:
            return RECOVERY_OUTCOME_PARTIAL
        return RECOVERY_OUTCOME_SUCCESS

    @staticmethod
    def _outcome_from_event(event) -> AgentTaskRecoveryOutcome:
        payload = event.payload if isinstance(event.payload, dict) else {}
        started_at = payload.get("started_at")
        completed_at = payload.get("completed_at")
        return AgentTaskRecoveryOutcome(
            recovery_id=event.event_id,
            task_id=event.task_id,
            source_failure_event_id=payload.get("source_failure_event_id"),
            planned_action=payload.get("planned_action"),
            executed_action=payload.get("executed_action"),
            status=payload.get("status"),
            reason=payload.get("reason"),
            started_at=datetime.fromisoformat(started_at) if started_at else event.occurred_at,
            completed_at=datetime.fromisoformat(completed_at) if completed_at else event.occurred_at,
        )

    @staticmethod
    def _require_text(value, field_name: str = "task_id") -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryOutcomeError(f"{field_name} is required and must be a non-empty string")
