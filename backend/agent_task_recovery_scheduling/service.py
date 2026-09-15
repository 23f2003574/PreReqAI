from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from backend.agent_task_recovery_guardrails import (
    APPROVED,
    LLMAgentTaskRecoveryPreflightApprovalService,
    LLMAgentTaskRecoveryPreflightAuthorizationService,
    LLMAgentTaskRecoveryPreflightAuthorizationValidationService,
)
from backend.storage import AtomicJsonFile

from .models import CANCELLED, INVALIDATED, SCHEDULED, AgentTaskRecoveryPreflightSchedule


class InvalidAgentTaskRecoverySchedulingError(ValueError):
    """Raised when schedule()/cancel()/get()/list() is given invalid
    arguments, or a preflight is not currently eligible to be scheduled
    (not approved, or cannot currently be authorized: unknown, superseded,
    invalidated, stale, or policy/guard-blocked)."""


class AgentTaskRecoveryScheduleStore(ABC):
    """Raw persistence for AgentTaskRecoveryPreflightSchedule records --
    indexed both by schedule_id (get()/cancel()'s own lookup key) and by
    (task_id, preflight_id) (schedule()'s own idempotency check), the
    same dual-index shape backend.agent_task_recovery_guardrails' own
    Commit #9 authorization store already establishes for a comparable
    case."""

    @abstractmethod
    def save(self, record: AgentTaskRecoveryPreflightSchedule) -> AgentTaskRecoveryPreflightSchedule:
        ...

    @abstractmethod
    def get(self, schedule_id: str) -> Optional[AgentTaskRecoveryPreflightSchedule]:
        ...

    @abstractmethod
    def get_for_preflight(self, task_id: str, preflight_id: str) -> Optional[AgentTaskRecoveryPreflightSchedule]:
        ...

    @abstractmethod
    def list_for_task(self, task_id: str) -> list:
        ...


class InMemoryAgentTaskRecoveryScheduleStore(AgentTaskRecoveryScheduleStore):
    """Stores AgentTaskRecoveryPreflightSchedule records in memory, for
    development and testing."""

    def __init__(self):
        self._by_id: dict = {}
        self._by_preflight: dict = {}
        self._by_task: dict = {}

    def save(self, record: AgentTaskRecoveryPreflightSchedule) -> AgentTaskRecoveryPreflightSchedule:
        stored = deepcopy(record)
        self._by_id[record.schedule_id] = stored
        self._by_preflight[(record.task_id, record.preflight_id)] = stored
        entries = self._by_task.setdefault(record.task_id, [])
        entries[:] = [entry for entry in entries if entry.schedule_id != record.schedule_id]
        entries.append(stored)
        return deepcopy(stored)

    def get(self, schedule_id: str) -> Optional[AgentTaskRecoveryPreflightSchedule]:
        record = self._by_id.get(schedule_id)
        return deepcopy(record) if record is not None else None

    def get_for_preflight(self, task_id: str, preflight_id: str) -> Optional[AgentTaskRecoveryPreflightSchedule]:
        record = self._by_preflight.get((task_id, preflight_id))
        return deepcopy(record) if record is not None else None

    def list_for_task(self, task_id: str) -> list:
        entries = self._by_task.get(task_id, [])
        return [deepcopy(entry) for entry in sorted(entries, key=lambda item: item.created_at)]


class JsonAgentTaskRecoveryScheduleStore(AgentTaskRecoveryScheduleStore):
    """Persists AgentTaskRecoveryPreflightSchedule records to a JSON
    file, keyed by schedule_id; the (task_id, preflight_id)/task_id
    lookups scan the (small) collection rather than maintaining a second
    on-disk index."""

    def __init__(self, path: str | Path):
        self.file = AtomicJsonFile(path, default_factory=dict)

    def save(self, record: AgentTaskRecoveryPreflightSchedule) -> AgentTaskRecoveryPreflightSchedule:
        records = self.file.read()
        records[record.schedule_id] = record.to_dict()
        self.file.write(records)
        return deepcopy(record)

    def get(self, schedule_id: str) -> Optional[AgentTaskRecoveryPreflightSchedule]:
        records = self.file.read()
        data = records.get(schedule_id)
        return AgentTaskRecoveryPreflightSchedule.from_dict(data) if data is not None else None

    def get_for_preflight(self, task_id: str, preflight_id: str) -> Optional[AgentTaskRecoveryPreflightSchedule]:
        for data in self.file.read().values():
            if data.get("task_id") == task_id and data.get("preflight_id") == preflight_id:
                return AgentTaskRecoveryPreflightSchedule.from_dict(data)
        return None

    def list_for_task(self, task_id: str) -> list:
        matching = [
            AgentTaskRecoveryPreflightSchedule.from_dict(data)
            for data in self.file.read().values()
            if data.get("task_id") == task_id
        ]
        return sorted(matching, key=lambda item: item.created_at)


class LLMAgentTaskRecoveryPreflightSchedulingService:
    """Defers approved recovery work to a later, explicit execution
    window -- never a second scheduler or queue (Rule: "Do not invent a
    scheduler or duplicate queue infrastructure"): schedule()/cancel()/
    get()/list() only ever persist a small, additive record through this
    package's own established Store ABC + InMemory/Json shape (mirrors
    backend.agent_task_recovery_guardrails' own Commit #9 authorization
    store) and reuse that SAME series' own approval/authorization/
    validation services for every actual eligibility decision -- never
    re-deriving any of them.

    Only a current, usable, APPROVED preflight can be scheduled (Rule:
    "Schedule only a current, usable, approved preflight"; "Stale,
    invalidated, superseded, or rejected preflights cannot be
    scheduled"): schedule() requires Commit #8's own approval_service.
    get() to report APPROVED, then calls Commit #9's own
    authorization_service.authorize() -- which itself already re-checks
    current/fresh/not-invalidated/guard-ALLOW before granting anything
    (Rule: "Validate authorization/guard conditions before scheduling")
    -- and propagates its own refusal as a scheduling error rather than
    re-implementing any of those checks itself.

    Re-checks eligibility live, never by mutating the stored record
    (Rule: "Re-check freshness/validity when determining whether a
    scheduled recovery is still eligible"): a still-SCHEDULED record
    whose own authorization_id no longer validates (Commit #10's own
    validate()) is returned by get()/list() as INVALIDATED -- a purely
    computed, read-time view, the same "effective status computed fresh
    on every read" discipline backend.agent_policy_risk_approval.
    LLMAgentRiskApprovalGate._effective() already establishes for a
    comparable case. The underlying stored `status` is never rewritten by
    this computation.

    cancel() is idempotent (Rule): an already-CANCELLED schedule is
    returned unchanged, first reason standing, the same convention every
    other write in this whole project's own task-recovery domain already
    follows.

    Never executes recovery (Rule): nothing here calls Commit #11's own
    consumption service, or anything from agent_task_event_analytics'
    own execution service -- this class only ever manages scheduling
    STATE.
    """

    def __init__(
        self,
        approval_service: LLMAgentTaskRecoveryPreflightApprovalService = None,
        authorization_service: LLMAgentTaskRecoveryPreflightAuthorizationService = None,
        validation_service: LLMAgentTaskRecoveryPreflightAuthorizationValidationService = None,
        store: AgentTaskRecoveryScheduleStore = None,
    ):
        self._approval_service = (
            approval_service if approval_service is not None else LLMAgentTaskRecoveryPreflightApprovalService()
        )
        self._authorization_service = (
            authorization_service
            if authorization_service is not None
            else LLMAgentTaskRecoveryPreflightAuthorizationService()
        )
        self._validation_service = (
            validation_service
            if validation_service is not None
            else LLMAgentTaskRecoveryPreflightAuthorizationValidationService()
        )
        self._store = store if store is not None else InMemoryAgentTaskRecoveryScheduleStore()

    def schedule(
        self, task_id: str, preflight_id: str, execute_at: datetime = None
    ) -> AgentTaskRecoveryPreflightSchedule:
        """Schedule task_id's exact, approved preflight_id for execution
        at execute_at (or "whenever eligible" when omitted). Idempotent:
        an already-SCHEDULED record for this exact preflight_id is
        returned unchanged.

        Raises:
            InvalidAgentTaskRecoverySchedulingError: If task_id/
                preflight_id is not a non-empty string, execute_at is
                given and is not a datetime, the preflight has not been
                approved, or it cannot currently be authorized (unknown,
                superseded, invalidated, stale, or policy/guard-blocked)
        """
        self._require_text(task_id, "task_id")
        self._require_text(preflight_id, "preflight_id")
        if execute_at is not None and not isinstance(execute_at, datetime):
            raise InvalidAgentTaskRecoverySchedulingError("execute_at must be a datetime when given")

        existing = self._store.get_for_preflight(task_id, preflight_id)
        if existing is not None and existing.status == SCHEDULED:
            return existing

        approval = self._approval_service.get(task_id, preflight_id)
        if approval is None or approval.status != APPROVED:
            raise InvalidAgentTaskRecoverySchedulingError(
                f"preflight {preflight_id!r} has not been approved and cannot be scheduled"
            )

        try:
            authorization = self._authorization_service.authorize(task_id, preflight_id)
        except Exception as error:
            raise InvalidAgentTaskRecoverySchedulingError(
                f"preflight {preflight_id!r} cannot be authorized for scheduling: {error}"
            ) from error

        record = AgentTaskRecoveryPreflightSchedule(
            task_id=task_id, preflight_id=preflight_id, authorization_id=authorization.authorization_id,
            execute_at=execute_at, status=SCHEDULED, created_at=datetime.now(timezone.utc),
            cancelled_at=None, cancellation_reason=None,
        )
        return self._store.save(record)

    def cancel(self, task_id: str, schedule_id: str, reason: str = None) -> AgentTaskRecoveryPreflightSchedule:
        """Cancel task_id's exact schedule_id. Idempotent: an already-
        cancelled schedule is returned unchanged, first reason standing.

        Raises:
            InvalidAgentTaskRecoverySchedulingError: If task_id/
                schedule_id is not a non-empty string, or schedule_id
                names no recorded schedule for task_id
        """
        self._require_text(task_id, "task_id")
        self._require_text(schedule_id, "schedule_id")

        record = self._store.get(schedule_id)
        if record is None or record.task_id != task_id:
            raise InvalidAgentTaskRecoverySchedulingError(
                f"no schedule {schedule_id!r} is recorded for task_id {task_id!r}"
            )
        if record.status == CANCELLED:
            return record

        resolved = replace(
            record, status=CANCELLED, cancelled_at=datetime.now(timezone.utc), cancellation_reason=reason
        )
        return self._store.save(resolved)

    def get(self, task_id: str, schedule_id: str) -> Optional[AgentTaskRecoveryPreflightSchedule]:
        """task_id's exact schedule_id, with its EFFECTIVE (live-
        recomputed, never persisted) status -- None if it does not exist
        or belongs to a different task_id.

        Raises:
            InvalidAgentTaskRecoverySchedulingError: If task_id or
                schedule_id is not a non-empty string
        """
        self._require_text(task_id, "task_id")
        self._require_text(schedule_id, "schedule_id")

        record = self._store.get(schedule_id)
        if record is None or record.task_id != task_id:
            return None
        return self._effective(record)

    def list(self, task_id: str) -> list:
        """Every schedule ever recorded for task_id, oldest to newest,
        each with its own effective (live-recomputed) status."""
        self._require_text(task_id, "task_id")
        return [self._effective(record) for record in self._store.list_for_task(task_id)]

    def _effective(self, record: AgentTaskRecoveryPreflightSchedule) -> AgentTaskRecoveryPreflightSchedule:
        if record.status != SCHEDULED:
            return record
        validation = self._validation_service.validate(record.task_id, record.authorization_id)
        if not validation.valid:
            return replace(record, status=INVALIDATED)
        return record

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoverySchedulingError(f"{field_name} is required and must be a non-empty string")
