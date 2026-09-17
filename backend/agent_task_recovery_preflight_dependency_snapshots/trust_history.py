from typing import Optional

from backend.agent_task_events import LLMAgentTaskEventQueryService, LLMAgentTaskEventService

from .models import AgentTaskRecoveryPreflightDependencySnapshotTrustHistoryRecord, AgentTaskRecoveryPreflightDependencySnapshotTrustResult

TRUST_HISTORY_EVENT_TYPE = "dependency_snapshot_trust_recorded"

# The fields idempotency compares to decide "is this the same verification
# state already recorded" -- history_id/recorded_at/verified_at are this
# record's own bookkeeping (a genuine repeat naturally reruns validate() at
# a new wall-clock moment), excluded here the same "content is stable,
# bookkeeping moves" way backend.agent_task_event_analytics.
# LLMAgentTaskRecoveryDecisionAuditService's own _IDENTITY_FIELDS already
# excludes decision_id/created_at for a comparable case.
_IDENTITY_FIELDS = (
    "preflight_id", "snapshot_id", "version", "trusted",
    "integrity_status", "signature_status", "blocking_reasons",
)


class InvalidAgentTaskRecoveryPreflightDependencySnapshotTrustHistoryError(ValueError):
    """Raised when record()/get()/latest() is given invalid arguments."""


class LLMAgentTaskRecoveryPreflightDependencySnapshotTrustHistoryService:
    """Persists Commit #6's own trust verdicts so past trust decisions
    stay auditable and reproducible -- never a generic audit framework
    (Rule: "Do not create a generic audit framework"): every read and
    write here goes through backend.agent_task_events' own already-
    existing append-only store, via LLMAgentTaskEventService.emit()/
    LLMAgentTaskEventQueryService.query(), recorded under a plain new
    event_type (TRUST_HISTORY_EVENT_TYPE) -- the exact same reuse pattern
    backend.agent_task_event_analytics.LLMAgentTaskRecoveryDecisionAuditService
    and backend.agent_task_recovery_schedule_dependencies.change_audit.py
    already establish for a comparable "persist a decision, don't build a
    second store" case.

    Append-only, never rewritten (Rule): record() only ever calls emit(),
    itself strictly append-only; nothing here ever mutates a Commit #6
    result or an already-recorded history entry.

    Records both trusted AND rejected verdicts (Rule): record() never
    filters on trust_result.trusted -- every call, whichever way it
    resolved, is persisted the same way.

    Idempotent by content (Rule: "Avoid duplicate records for the same
    verification state"): before emitting anything, record() checks
    task_id/snapshot_id's already-recorded history for one whose own
    preflight_id/version/trusted/integrity_status/signature_status/
    blocking_reasons all already match -- if found, that existing record
    is returned unchanged rather than duplicated. A genuinely new
    validate() call whose verdict changed (even a single reason word)
    always records a fresh entry.

    Recording never alters the trust decision (Rule: "without making
    history persistence alter the trust decision"): record() takes an
    already-computed AgentTaskRecoveryPreflightDependencySnapshotTrustResult
    as a plain argument -- it never calls validate() itself, never holds
    a reference to Commit #6's own service, and cannot influence what
    that result was.

    Read-only with respect to recovery/scheduling (Rule): this class
    holds no reference to anything that could execute, authorize, or
    reschedule recovery.
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
        self, task_id: str, snapshot_id: str, trust_result: AgentTaskRecoveryPreflightDependencySnapshotTrustResult
    ) -> AgentTaskRecoveryPreflightDependencySnapshotTrustHistoryRecord:
        """Persist trust_result's own evidence for task_id/snapshot_id.
        Idempotent: an already-recorded, identical verification state is
        returned unchanged rather than duplicated.

        Raises:
            InvalidAgentTaskRecoveryPreflightDependencySnapshotTrustHistoryError:
                If task_id/snapshot_id is not a non-empty string,
                trust_result is not an AgentTaskRecoveryPreflightDependency
                SnapshotTrustResult, or its own task_id/snapshot_id does
                not match the ones given
        """
        self._require_text(task_id, "task_id")
        self._require_text(snapshot_id, "snapshot_id")
        if not isinstance(trust_result, AgentTaskRecoveryPreflightDependencySnapshotTrustResult):
            raise InvalidAgentTaskRecoveryPreflightDependencySnapshotTrustHistoryError(
                "trust_result must be an AgentTaskRecoveryPreflightDependencySnapshotTrustResult"
            )
        if trust_result.task_id != task_id or trust_result.snapshot_id != snapshot_id:
            raise InvalidAgentTaskRecoveryPreflightDependencySnapshotTrustHistoryError(
                f"trust_result does not belong to task_id {task_id!r} / snapshot_id {snapshot_id!r}"
            )

        existing = self._find_matching(task_id, snapshot_id, trust_result)
        if existing is not None:
            return existing

        payload = {
            "preflight_id": trust_result.preflight_id,
            "snapshot_id": trust_result.snapshot_id,
            "version": trust_result.version,
            "trusted": trust_result.trusted,
            "integrity_status": trust_result.integrity_status,
            "signature_status": trust_result.signature_status,
            "blocking_reasons": list(trust_result.blocking_reasons),
            "verified_at": trust_result.validated_at.isoformat(),
        }
        event = self._event_service.emit(task_id, TRUST_HISTORY_EVENT_TYPE, payload=payload)
        return self._record_from_event(event)

    def get(self, task_id: str, snapshot_id: str) -> list:
        """Every trust history record for task_id's exact snapshot_id,
        oldest to newest -- the complete, never-overwritten history.

        Raises:
            InvalidAgentTaskRecoveryPreflightDependencySnapshotTrustHistoryError:
                If task_id or snapshot_id is not a non-empty string
        """
        self._require_text(task_id, "task_id")
        self._require_text(snapshot_id, "snapshot_id")

        events = self._query_service.query(task_id=task_id, event_types=[TRUST_HISTORY_EVENT_TYPE])
        records = [self._record_from_event(event) for event in events]
        return [record for record in records if record.snapshot_id == snapshot_id]

    def latest(self, task_id: str, snapshot_id: str) -> Optional[AgentTaskRecoveryPreflightDependencySnapshotTrustHistoryRecord]:
        """task_id/snapshot_id's most recently recorded trust history
        entry, or None when nothing has ever been recorded."""
        records = self.get(task_id, snapshot_id)
        return records[-1] if records else None

    def _find_matching(
        self, task_id: str, snapshot_id: str, trust_result: AgentTaskRecoveryPreflightDependencySnapshotTrustResult
    ) -> Optional[AgentTaskRecoveryPreflightDependencySnapshotTrustHistoryRecord]:
        for record in self.get(task_id, snapshot_id):
            if all(getattr(record, field) == getattr(trust_result, field) for field in _IDENTITY_FIELDS):
                return record
        return None

    @staticmethod
    def _record_from_event(event) -> AgentTaskRecoveryPreflightDependencySnapshotTrustHistoryRecord:
        payload = event.payload if isinstance(event.payload, dict) else {}
        verified_at = payload.get("verified_at")
        if isinstance(verified_at, str):
            from datetime import datetime
            verified_at = datetime.fromisoformat(verified_at)
        return AgentTaskRecoveryPreflightDependencySnapshotTrustHistoryRecord(
            task_id=event.task_id,
            preflight_id=payload.get("preflight_id"),
            snapshot_id=payload.get("snapshot_id"),
            version=payload.get("version"),
            trusted=bool(payload.get("trusted")),
            integrity_status=payload.get("integrity_status"),
            signature_status=payload.get("signature_status"),
            blocking_reasons=tuple(payload.get("blocking_reasons") or ()),
            verified_at=verified_at,
            recorded_at=event.occurred_at,
            history_id=event.event_id,
        )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryPreflightDependencySnapshotTrustHistoryError(
                f"{field_name} is required and must be a non-empty string"
            )
