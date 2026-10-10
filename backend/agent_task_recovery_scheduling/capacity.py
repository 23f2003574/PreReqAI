from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

from backend.session import ExecutionConcurrencyError, ExecutionConcurrencyService
from backend.storage import AtomicJsonFile

from .validation import LLMAgentTaskRecoveryPreflightScheduleValidationService

DEFAULT_CAPACITY_SCOPE_ID = "agent_task_recovery"
ADMITTED = "admitted"


class InvalidAgentTaskRecoveryScheduleCapacityError(ValueError):
    """Raised when check()/admit() is given invalid arguments, or a
    schedule cannot currently be admitted (ineligible, or no spare
    capacity)."""


@dataclass(frozen=True)
class AgentTaskRecoveryScheduleCapacityResult:
    """LLMAgentTaskRecoveryPreflightScheduleCapacityService.check()'s
    read-only, explainable capacity verdict -- re-checked fresh on every
    call (Rule: "Re-check capacity rather than trusting an earlier
    scheduling decision"), never cached or persisted."""

    task_id: str
    schedule_id: Optional[str]
    capacity_available: bool
    eligible: Optional[bool]
    blocking_reasons: tuple
    checked_at: datetime


@dataclass(frozen=True)
class AgentTaskRecoveryScheduleAdmission:
    """Immutable record that one EXACT schedule was admitted into the
    existing backend.session.ExecutionConcurrencyService's own running
    set -- never an execution itself (Rule: "admit() ... must not execute
    recovery"). One record per schedule_id, ever (Rule: "admit() must be
    idempotent")."""

    task_id: str
    schedule_id: str
    status: str
    admitted_at: datetime
    admission_id: str = field(default_factory=lambda: str(uuid4()))

    def to_dict(self) -> dict:
        data = asdict(self)
        data["admitted_at"] = self.admitted_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "AgentTaskRecoveryScheduleAdmission":
        payload = dict(data)
        value = payload.get("admitted_at")
        if isinstance(value, str):
            payload["admitted_at"] = datetime.fromisoformat(value)
        return cls(**payload)


class AgentTaskRecoveryScheduleAdmissionStore(ABC):
    """Raw persistence for AgentTaskRecoveryScheduleAdmission records,
    keyed by schedule_id -- the same single-record-per-key shape this
    whole series already establishes (Rule: "Persist admission state
    only if the repository already has a suitable ... pattern")."""

    @abstractmethod
    def save(self, record: AgentTaskRecoveryScheduleAdmission) -> AgentTaskRecoveryScheduleAdmission:
        ...

    @abstractmethod
    def get(self, schedule_id: str) -> Optional[AgentTaskRecoveryScheduleAdmission]:
        ...


class InMemoryAgentTaskRecoveryScheduleAdmissionStore(AgentTaskRecoveryScheduleAdmissionStore):
    def __init__(self):
        self._records: dict = {}

    def save(self, record: AgentTaskRecoveryScheduleAdmission) -> AgentTaskRecoveryScheduleAdmission:
        stored = deepcopy(record)
        self._records[record.schedule_id] = stored
        return deepcopy(stored)

    def get(self, schedule_id: str) -> Optional[AgentTaskRecoveryScheduleAdmission]:
        record = self._records.get(schedule_id)
        return deepcopy(record) if record is not None else None


class JsonAgentTaskRecoveryScheduleAdmissionStore(AgentTaskRecoveryScheduleAdmissionStore):
    def __init__(self, path: str | Path):
        self.file = AtomicJsonFile(path, default_factory=dict)

    def save(self, record: AgentTaskRecoveryScheduleAdmission) -> AgentTaskRecoveryScheduleAdmission:
        records = self.file.read()
        records[record.schedule_id] = record.to_dict()
        self.file.write(records)
        return deepcopy(record)

    def get(self, schedule_id: str) -> Optional[AgentTaskRecoveryScheduleAdmission]:
        data = self.file.read().get(schedule_id)
        return AgentTaskRecoveryScheduleAdmission.from_dict(data) if data is not None else None


class LLMAgentTaskRecoveryPreflightScheduleCapacityService:
    """Capacity-aware admission control for scheduled recovery work --
    never a new worker pool, semaphore, or quota system (Rule): the ONLY
    actual capacity enforcement anywhere in this class is
    backend.session.ExecutionConcurrencyService's own existing
    register()/can_start()/acquire() -- a real, already-existing, scope-
    based concurrency limiter -- reused directly under a fixed scope_id
    rather than reimplemented; schedule eligibility is reused from Commit
    #2's own is_executable(), never re-derived.

    Never bypasses guardrails (Rule): check()/admit() always also confirm
    Commit #2's own is_executable() -- which itself already reuses Commit
    #10-of-agent_task_recovery_guardrails' authorization validation (risk/
    policy/authorization) -- capacity alone can never make an otherwise-
    ineligible schedule admittable.

    Graceful degradation (the same "optional collaborator, degrade rather
    than guess" pattern this whole project already establishes): with no
    concurrency_service configured, capacity is always reported available
    -- this service invents no capacity number of its own to enforce.

    admit() is idempotent by schedule_id (Rule): a schedule already
    admitted returns its original record unchanged, and
    ExecutionConcurrencyService.acquire() (which itself raises for a
    repeat job_id) is never called a second time for it.

    Never executes recovery (Rule): admit() only ever acquires a
    concurrency slot -- it never calls Commit #4(-of-agent_task_event_
    analytics)'s own execution service or Commit #11(-of-agent_task_
    recovery_guardrails)'s own consumption service. Keeps scheduling and
    execution state separate (Rule): admission state lives in its own
    store, entirely apart from Commit #1's own schedule records.
    """

    def __init__(
        self,
        validation_service: LLMAgentTaskRecoveryPreflightScheduleValidationService = None,
        concurrency_service: ExecutionConcurrencyService = None,
        scope_id: str = DEFAULT_CAPACITY_SCOPE_ID,
        max_running: int = None,
        store: AgentTaskRecoveryScheduleAdmissionStore = None,
    ):
        self._validation_service = (
            validation_service if validation_service is not None else LLMAgentTaskRecoveryPreflightScheduleValidationService()
        )
        self._concurrency_service = concurrency_service
        self._scope_id = scope_id
        self._store = store if store is not None else InMemoryAgentTaskRecoveryScheduleAdmissionStore()
        if self._concurrency_service is not None and max_running is not None:
            self._concurrency_service.register(self._scope_id, max_running)

    def check(self, task_id: str, schedule_id: str = None) -> AgentTaskRecoveryScheduleCapacityResult:
        """Read-only capacity + eligibility check, re-evaluated fresh
        every call.

        Raises:
            InvalidAgentTaskRecoveryScheduleCapacityError: If task_id is
                not a non-empty string, or schedule_id is given and is
                not a non-empty string
        """
        self._require_text(task_id, "task_id")
        if schedule_id is not None:
            self._require_text(schedule_id, "schedule_id")

        capacity_available = self._has_capacity()
        blocking_reasons = []
        if not capacity_available:
            blocking_reasons.append("no spare execution capacity is currently available")

        eligible = None
        if schedule_id is not None:
            eligible = self._validation_service.is_executable(task_id, schedule_id)
            if not eligible:
                blocking_reasons.append("schedule is not currently executable")

        return AgentTaskRecoveryScheduleCapacityResult(
            task_id=task_id, schedule_id=schedule_id, capacity_available=capacity_available,
            eligible=eligible, blocking_reasons=tuple(blocking_reasons), checked_at=datetime.now(timezone.utc),
        )

    def admit(self, task_id: str, schedule_id: str) -> AgentTaskRecoveryScheduleAdmission:
        """Admit task_id's exact schedule_id into the existing
        concurrency scope. Idempotent: an already-admitted schedule_id
        returns its original record unchanged.

        Raises:
            InvalidAgentTaskRecoveryScheduleCapacityError: If task_id or
                schedule_id is not a non-empty string, the schedule is
                not currently eligible, or no spare capacity is
                available
        """
        self._require_text(task_id, "task_id")
        self._require_text(schedule_id, "schedule_id")

        existing = self._store.get(schedule_id)
        if existing is not None:
            return existing

        result = self.check(task_id, schedule_id)
        if result.blocking_reasons:
            raise InvalidAgentTaskRecoveryScheduleCapacityError(
                f"schedule {schedule_id!r} cannot be admitted: " + "; ".join(result.blocking_reasons)
            )

        if self._concurrency_service is not None:
            try:
                self._concurrency_service.acquire(self._scope_id, schedule_id)
            except ExecutionConcurrencyError as error:
                raise InvalidAgentTaskRecoveryScheduleCapacityError(
                    f"could not acquire capacity for schedule {schedule_id!r}: {error}"
                ) from error

        admission = AgentTaskRecoveryScheduleAdmission(
            task_id=task_id, schedule_id=schedule_id, status=ADMITTED, admitted_at=datetime.now(timezone.utc)
        )
        return self._store.save(admission)

    def _has_capacity(self) -> bool:
        if self._concurrency_service is None:
            return True
        try:
            return self._concurrency_service.can_start(self._scope_id)
        except ExecutionConcurrencyError:
            return False

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryScheduleCapacityError(
                f"{field_name} is required and must be a non-empty string"
            )
