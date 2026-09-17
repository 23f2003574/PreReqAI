from datetime import datetime
from typing import Optional

from backend.agent_task_events import LLMAgentTaskEventQueryService, LLMAgentTaskEventService

from .models import AgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryAuditRecord, AgentTaskRecoveryPreflightDependencySnapshotTrustRevalidationResult

TRUST_RECOVERY_AUDIT_EVENT_TYPE = "dependency_snapshot_trust_recovery_recorded"

# Bookkeeping (audit_id/recorded_at/revalidated_at) excluded, the same
# "content is stable, bookkeeping moves" discipline Commit #7's own
# trust_history.py and backend.agent_task_event_analytics.
# LLMAgentTaskRecoveryDecisionAuditService already establish.
_IDENTITY_FIELDS = (
    "preflight_id", "old_snapshot_id", "new_snapshot_id", "version", "action",
    "old_trusted", "old_integrity_status", "old_signature_status",
    "new_trusted", "new_integrity_status", "new_signature_status", "reason",
)


class InvalidAgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryAuditError(ValueError):
    """Raised when record()/get()/list() is given invalid arguments."""


class LLMAgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryAuditService:
    """Persists Commit #10's own revalidation outcomes so the system has
    a durable audit trail of why dependency evidence became trusted or
    remained unusable -- never a generic audit system (Rule: "Do not
    create a new generic audit system"): every read and write here goes
    through backend.agent_task_events' own already-existing append-only
    store, via LLMAgentTaskEventService.emit()/
    LLMAgentTaskEventQueryService.query(), recorded under a plain new
    event_type -- the exact same reuse pattern Commit #7's own
    trust_history.py and backend.agent_task_event_analytics.
    LLMAgentTaskRecoveryDecisionAuditService already establish for a
    comparable "persist a decision, don't build a second store" case.

    Append-only (Rule): record() only ever calls emit(); never rewrites
    or reads back a Commit #10 result to alter it.

    Records BOTH successful replacement and failed revalidation (Rule:
    "Preserve failed trust-recovery attempts as well as successful
    ones"): record() never filters on action -- REUSED/REPLACED/
    REVALIDATION_FAILED/REVALIDATION_MISSING are all persisted the same
    way.

    Idempotent by content (Rule): before emitting anything, record()
    checks task_id/snapshot_id's already-recorded audits for one whose
    own preflight_id/old_snapshot_id/new_snapshot_id/version/action/
    old+new trusted+integrity_status+signature_status/reason all already
    match -- if found, that existing record is returned unchanged.

    Recording never influences the trust decision (Rule: "Never change
    trust decisions based on audit success/failure"): record() takes an
    already-computed Commit #10 result as a plain argument -- it never
    calls revalidate() itself and holds no reference to Commit #10's own
    service.

    Read-only with respect to recovery/scheduling (Rule): no such
    collaborator is held; nothing here executes, schedules, or
    authorizes anything.
    """

    def __init__(
        self,
        event_service: LLMAgentTaskEventService = None,
        query_service: LLMAgentTaskEventQueryService = None,
    ):
        self._event_service = event_service if event_service is not None else LLMAgentTaskEventService()
        self._query_service = (
            query_service if query_service is not None else LLMAgentTaskEventQueryService(store=self._event_service.store)
        )

    def record(
        self, task_id: str, snapshot_id: str, revalidation_result: AgentTaskRecoveryPreflightDependencySnapshotTrustRevalidationResult
    ) -> AgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryAuditRecord:
        """Persist revalidation_result's own evidence for task_id/
        snapshot_id. Idempotent: an already-recorded, identical outcome
        is returned unchanged rather than duplicated.

        Raises:
            InvalidAgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryAuditError:
                If task_id/snapshot_id is not a non-empty string,
                revalidation_result is not an AgentTaskRecoveryPreflight
                DependencySnapshotTrustRevalidationResult, or its own
                task_id/old_snapshot_id does not match the ones given
        """
        self._require_text(task_id, "task_id")
        self._require_text(snapshot_id, "snapshot_id")
        if not isinstance(revalidation_result, AgentTaskRecoveryPreflightDependencySnapshotTrustRevalidationResult):
            raise InvalidAgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryAuditError(
                "revalidation_result must be an AgentTaskRecoveryPreflightDependencySnapshotTrustRevalidationResult"
            )
        if revalidation_result.task_id != task_id or revalidation_result.old_snapshot_id != snapshot_id:
            raise InvalidAgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryAuditError(
                f"revalidation_result does not belong to task_id {task_id!r} / snapshot_id {snapshot_id!r}"
            )

        old_trust = revalidation_result.old_trust
        new_trust = revalidation_result.new_trust
        reason = (
            "; ".join(new_trust.blocking_reasons) if new_trust is not None and new_trust.blocking_reasons
            else ("; ".join(old_trust.blocking_reasons) if old_trust is not None and old_trust.blocking_reasons else None)
        )

        payload = {
            "preflight_id": revalidation_result.preflight_id,
            "old_snapshot_id": revalidation_result.old_snapshot_id,
            "new_snapshot_id": revalidation_result.new_snapshot_id,
            "version": new_trust.version if new_trust is not None else None,
            "action": revalidation_result.action,
            "old_trusted": old_trust.trusted if old_trust is not None else None,
            "old_integrity_status": old_trust.integrity_status if old_trust is not None else None,
            "old_signature_status": old_trust.signature_status if old_trust is not None else None,
            "new_trusted": new_trust.trusted if new_trust is not None else None,
            "new_integrity_status": new_trust.integrity_status if new_trust is not None else None,
            "new_signature_status": new_trust.signature_status if new_trust is not None else None,
            "reason": reason,
            "revalidated_at": revalidation_result.revalidated_at.isoformat(),
        }

        existing = self._find_matching(task_id, snapshot_id, payload)
        if existing is not None:
            return existing

        event = self._event_service.emit(task_id, TRUST_RECOVERY_AUDIT_EVENT_TYPE, payload=payload)
        return self._record_from_event(event)

    def get(self, task_id: str, snapshot_id: str) -> list:
        """Every trust-recovery audit record for task_id's exact
        old_snapshot_id, oldest to newest.

        Raises:
            InvalidAgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryAuditError:
                If task_id or snapshot_id is not a non-empty string
        """
        self._require_text(task_id, "task_id")
        self._require_text(snapshot_id, "snapshot_id")
        return [record for record in self.list(task_id) if record.old_snapshot_id == snapshot_id]

    def list(self, task_id: str) -> list:
        """Every trust-recovery audit record ever recorded for task_id,
        across every snapshot_id, oldest to newest.

        Raises:
            InvalidAgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryAuditError:
                If task_id is not a non-empty string
        """
        self._require_text(task_id, "task_id")
        events = self._query_service.query(task_id=task_id, event_types=[TRUST_RECOVERY_AUDIT_EVENT_TYPE])
        return [self._record_from_event(event) for event in events]

    def _find_matching(self, task_id, snapshot_id, payload):
        for record in self.get(task_id, snapshot_id):
            if all(getattr(record, field) == payload[field] for field in _IDENTITY_FIELDS):
                return record
        return None

    @staticmethod
    def _record_from_event(event) -> AgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryAuditRecord:
        payload = event.payload if isinstance(event.payload, dict) else {}
        revalidated_at = payload.get("revalidated_at")
        if isinstance(revalidated_at, str):
            revalidated_at = datetime.fromisoformat(revalidated_at)
        return AgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryAuditRecord(
            task_id=event.task_id,
            preflight_id=payload.get("preflight_id"),
            old_snapshot_id=payload.get("old_snapshot_id"),
            new_snapshot_id=payload.get("new_snapshot_id"),
            version=payload.get("version"),
            action=payload.get("action"),
            old_trusted=payload.get("old_trusted"),
            old_integrity_status=payload.get("old_integrity_status"),
            old_signature_status=payload.get("old_signature_status"),
            new_trusted=payload.get("new_trusted"),
            new_integrity_status=payload.get("new_integrity_status"),
            new_signature_status=payload.get("new_signature_status"),
            reason=payload.get("reason"),
            revalidated_at=revalidated_at,
            recorded_at=event.occurred_at,
            audit_id=event.event_id,
        )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryPreflightDependencySnapshotTrustRecoveryAuditError(
                f"{field_name} is required and must be a non-empty string"
            )
