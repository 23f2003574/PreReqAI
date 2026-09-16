from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from backend.agent_task_events import LLMAgentTaskEventQueryService, LLMAgentTaskEventService

from .change_execution import APPLIED, AgentTaskRecoveryScheduleChangeActionResult

# The event_type this service records every audit entry under, through
# backend.agent_task_events' own already-existing LLMAgentTaskEventService.
# emit()/LLMAgentTaskEventQueryService.query() -- never a new, second
# audit store (Rule: "Reuse existing task-event, recovery audit ...
# persistence where possible" / "Do not create a new generic audit
# framework"), the exact same reuse pattern backend.agent_task_event_
# analytics.LLMAgentTaskRecoveryDecisionAuditService already establishes
# for a comparable case (Commit #8-of-that-series' own recovery
# recommendations, recorded under RECOVERY_DECISION_EVENT_TYPE).
DEPENDENCY_CHANGE_AUDIT_EVENT_TYPE = "dependency_change_audit_recorded"

# The AgentTaskRecoveryScheduleChangeActionResult fields idempotency
# compares to decide "is this the exact same change application already
# recorded" -- audit_id/recorded_at are this record's own bookkeeping
# (always new on a genuine repeat), never part of the comparison, the
# same "content is stable, bookkeeping moves" discipline backend.
# agent_task_event_analytics.LLMAgentTaskRecoveryDecisionAuditService's
# own _IDENTITY_FIELDS already establish for a comparable case.
_IDENTITY_FIELDS = (
    "preflight_id", "dependency_id", "action", "status", "new_schedule_id",
    "previous_status", "resulting_status", "reason",
)


class InvalidAgentTaskRecoveryScheduleDependencyChangeAuditError(ValueError):
    """Raised when record()/get()/list() is given invalid arguments, or
    record() is given a change_result that is not an
    AgentTaskRecoveryScheduleChangeActionResult naming this exact
    task_id/schedule_id."""


@dataclass(frozen=True)
class AgentTaskRecoveryScheduleDependencyChangeAudit:
    """One durable, append-only audit entry recording exactly one Commit
    #11 change application -- every field the Goal's own "Record:" list
    names, and nothing this service re-derives a second way: every one
    of them is read straight off the AgentTaskRecoveryScheduleChangeActionResult
    record() was given, itself already carrying Commit #10's own fresh
    plan item's dependency evidence (Rule: "Preserve the exact
    dependency evidence used by the planner" -- captured at the exact
    moment Commit #11 decided what to do, never recomputed afterward,
    when state may have already moved on again).

    success is exactly `status == APPLIED` -- a convenience view over
    Commit #11's own three-way status vocabulary (applied/rejected/
    failed), reused verbatim rather than a second true/false scheme.
    """

    audit_id: str
    task_id: str
    schedule_id: str
    preflight_id: Optional[str]
    dependency_id: Optional[str]
    action: Optional[str]
    status: str
    success: bool
    new_schedule_id: Optional[str]
    previous_status: Optional[str]
    resulting_status: Optional[str]
    reason: str
    dependency_evidence: tuple
    recorded_at: datetime


class LLMAgentTaskRecoveryPreflightScheduleDependencyChangeAuditService:
    """Durable audit trail for every Commit #11 dependency-driven change
    application -- never a new generic audit framework (Rule): every
    read and write here goes through backend.agent_task_events' own
    already-existing append-only store, via LLMAgentTaskEventService.
    emit()/LLMAgentTaskEventQueryService.query(), recorded under a plain
    new event_type (DEPENDENCY_CHANGE_AUDIT_EVENT_TYPE) -- the exact
    same reuse pattern backend.agent_task_event_analytics.
    LLMAgentTaskRecoveryDecisionAuditService already establishes.

    Append-only by construction (Rule: "Append-only history"): record()
    only ever calls emit(), itself strictly append-only, and never
    rewrites or deletes anything. Never alters a scheduling decision
    (Rule: "Never alter scheduling decisions itself") -- this class
    holds no reference to LLMAgentTaskRecoveryPreflightSchedulingService,
    Commit #10's own planner, or Commit #11's own change service at all;
    it only ever reads the ALREADY-DECIDED
    AgentTaskRecoveryScheduleChangeActionResult record() is handed.

    Audits both outcomes (Rule: "Audit both successful and failed change
    applications"): record() accepts a change_result of ANY Commit #11
    status (applied/rejected/failed) uniformly -- there is no branch
    anywhere in this class that skips a failed or rejected one.

    record() is idempotent for the exact same change application (Rule:
    "Prevent duplicate records for the same change application"): before
    emitting anything, it checks task_id/schedule_id's already-recorded
    audits for one whose own preflight_id/dependency_id/action/status/
    new_schedule_id/previous_status/resulting_status/reason all already
    match -- if found, that existing audit is returned unchanged rather
    than recording a duplicate. The same content-based idempotency
    convention LLMAgentTaskRecoveryDecisionAuditService's own record()
    already establishes, reused here rather than a new scheme.

    get()/list() are both plain reads through query() (Rule: retrieval
    is deterministic, inherited directly from that service's own
    already-deterministic ordering) -- get(task_id, schedule_id) is
    every audit for that exact schedule_id, list(task_id) is every
    audit for task_id across every schedule_id it has ever touched, both
    oldest to newest, neither ever raises for a task_id/schedule_id with
    no recorded audits at all (an empty list, the same tolerant-read
    discipline every other read path in this task family already
    establishes).

    Integrates with Commit #11 (Rule: "Integrate with the #11 change-
    execution service") by being accepted as that service's own optional
    audit_service constructor argument -- see
    LLMAgentTaskRecoveryPreflightScheduleDependencyChangeService's own
    docstring: when wired in, every apply_schedule() call (direct, or
    from inside apply()'s own batch loop) records its own result here
    automatically, for every one of applied/rejected/failed.
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
        self, task_id: str, schedule_id: str, change_result: AgentTaskRecoveryScheduleChangeActionResult
    ) -> AgentTaskRecoveryScheduleDependencyChangeAudit:
        """Record change_result's own outcome for task_id's exact
        schedule_id. Idempotent: an already-recorded, identical change
        application is returned unchanged rather than duplicated.

        Raises:
            InvalidAgentTaskRecoveryScheduleDependencyChangeAuditError:
                If task_id/schedule_id is not a non-empty string,
                change_result is not an
                AgentTaskRecoveryScheduleChangeActionResult, or
                change_result.task_id/schedule_id does not match
                task_id/schedule_id
        """
        self._require_text(task_id, "task_id")
        self._require_text(schedule_id, "schedule_id")
        if not isinstance(change_result, AgentTaskRecoveryScheduleChangeActionResult):
            raise InvalidAgentTaskRecoveryScheduleDependencyChangeAuditError(
                "change_result must be an AgentTaskRecoveryScheduleChangeActionResult"
            )
        if change_result.task_id != task_id or change_result.schedule_id != schedule_id:
            raise InvalidAgentTaskRecoveryScheduleDependencyChangeAuditError(
                "change_result does not name this exact task_id/schedule_id"
            )

        existing = self._find_matching(task_id, schedule_id, change_result)
        if existing is not None:
            return existing

        payload = {
            "schedule_id": schedule_id,
            "preflight_id": change_result.preflight_id,
            "dependency_id": change_result.dependency_id,
            "action": change_result.action,
            "status": change_result.status,
            "new_schedule_id": change_result.new_schedule_id,
            "previous_status": change_result.previous_status,
            "resulting_status": change_result.resulting_status,
            "reason": change_result.reason,
            "dependency_evidence": list(change_result.dependency_evidence),
        }
        event = self._event_service.emit(task_id, DEPENDENCY_CHANGE_AUDIT_EVENT_TYPE, payload=payload)
        return self._audit_from_event(event)

    def get(self, task_id: str, schedule_id: str) -> list:
        """Every audit ever recorded for task_id's exact schedule_id,
        oldest to newest. Never raises for a schedule_id with no
        recorded audits -- an empty list.

        Raises:
            InvalidAgentTaskRecoveryScheduleDependencyChangeAuditError:
                If task_id or schedule_id is not a non-empty string
        """
        self._require_text(task_id, "task_id")
        self._require_text(schedule_id, "schedule_id")
        return [audit for audit in self.list(task_id) if audit.schedule_id == schedule_id]

    def list(self, task_id: str) -> list:
        """Every audit ever recorded for task_id, across every
        schedule_id, oldest to newest.

        Raises:
            InvalidAgentTaskRecoveryScheduleDependencyChangeAuditError:
                If task_id is not a non-empty string
        """
        self._require_text(task_id, "task_id")
        events = self._query_service.query(task_id=task_id, event_types=(DEPENDENCY_CHANGE_AUDIT_EVENT_TYPE,))
        return [self._audit_from_event(event) for event in events]

    def _find_matching(
        self, task_id: str, schedule_id: str, change_result: AgentTaskRecoveryScheduleChangeActionResult
    ) -> Optional[AgentTaskRecoveryScheduleDependencyChangeAudit]:
        for audit in self.get(task_id, schedule_id):
            if all(getattr(audit, field) == getattr(change_result, field) for field in _IDENTITY_FIELDS):
                return audit
        return None

    @staticmethod
    def _audit_from_event(event) -> AgentTaskRecoveryScheduleDependencyChangeAudit:
        payload = event.payload if isinstance(event.payload, dict) else {}
        status = payload.get("status")
        return AgentTaskRecoveryScheduleDependencyChangeAudit(
            audit_id=event.event_id, task_id=event.task_id, schedule_id=payload.get("schedule_id"),
            preflight_id=payload.get("preflight_id"), dependency_id=payload.get("dependency_id"),
            action=payload.get("action"), status=status, success=(status == APPLIED),
            new_schedule_id=payload.get("new_schedule_id"), previous_status=payload.get("previous_status"),
            resulting_status=payload.get("resulting_status"), reason=payload.get("reason"),
            dependency_evidence=tuple(payload.get("dependency_evidence") or ()), recorded_at=event.occurred_at,
        )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryScheduleDependencyChangeAuditError(
                f"{field_name} is required and must be a non-empty string"
            )
