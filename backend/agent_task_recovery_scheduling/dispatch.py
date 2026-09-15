from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

from backend.storage import AtomicJsonFile

from .service import LLMAgentTaskRecoveryPreflightSchedulingService
from .validation import LLMAgentTaskRecoveryPreflightScheduleValidationService

DISPATCHED = "dispatched"


class InvalidAgentTaskRecoveryScheduleDispatchError(ValueError):
    """Raised when dispatch()/get() is given invalid arguments, or a
    schedule is not currently eligible to dispatch (missing, cancelled,
    stale/invalid, or its execution window has not yet arrived)."""


@dataclass(frozen=True)
class AgentTaskRecoveryScheduleDispatch:
    """Immutable, durable record that one EXACT Commit #1 schedule was
    handed off to the existing task queue/dispatch mechanism -- never an
    execution itself (Rule: "Do not execute recovery in this service").
    One record per (task_id, schedule_id), ever (Rule: "Prevent duplicate
    dispatch of the same schedule").

    queue_reference is whatever identifying value the real queue/dispatch
    collaborator returned (Rule: "queue/execution reference where
    supported") -- None when no such collaborator was supplied at all,
    never fabricated.
    """

    task_id: str
    schedule_id: str
    preflight_id: str
    dispatched_at: datetime
    status: str
    queue_reference: Optional[str]
    dispatch_id: str = field(default_factory=lambda: str(uuid4()))

    def to_dict(self) -> dict:
        data = asdict(self)
        data["dispatched_at"] = self.dispatched_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "AgentTaskRecoveryScheduleDispatch":
        payload = dict(data)
        value = payload.get("dispatched_at")
        if isinstance(value, str):
            payload["dispatched_at"] = datetime.fromisoformat(value)
        return cls(**payload)


class AgentTaskRecoveryScheduleDispatchStore(ABC):
    """Raw persistence for AgentTaskRecoveryScheduleDispatch records --
    indexed both by dispatch_id (get()'s own lookup key) and by
    (task_id, schedule_id) (dispatch()'s own duplicate-prevention check),
    the same dual-index shape this whole series already establishes for
    a comparable case (Commit #9-of-agent_task_recovery_guardrails'
    authorization store)."""

    @abstractmethod
    def save(self, record: AgentTaskRecoveryScheduleDispatch) -> AgentTaskRecoveryScheduleDispatch:
        ...

    @abstractmethod
    def get(self, dispatch_id: str) -> Optional[AgentTaskRecoveryScheduleDispatch]:
        ...

    @abstractmethod
    def get_for_schedule(self, task_id: str, schedule_id: str) -> Optional[AgentTaskRecoveryScheduleDispatch]:
        ...

    @abstractmethod
    def list_for_task(self, task_id: str) -> list:
        ...


class InMemoryAgentTaskRecoveryScheduleDispatchStore(AgentTaskRecoveryScheduleDispatchStore):
    """Stores AgentTaskRecoveryScheduleDispatch records in memory, for
    development and testing."""

    def __init__(self):
        self._by_id: dict = {}
        self._by_schedule: dict = {}
        self._by_task: dict = {}

    def save(self, record: AgentTaskRecoveryScheduleDispatch) -> AgentTaskRecoveryScheduleDispatch:
        stored = deepcopy(record)
        self._by_id[record.dispatch_id] = stored
        self._by_schedule[(record.task_id, record.schedule_id)] = stored
        self._by_task.setdefault(record.task_id, []).append(stored)
        return deepcopy(stored)

    def get(self, dispatch_id: str) -> Optional[AgentTaskRecoveryScheduleDispatch]:
        record = self._by_id.get(dispatch_id)
        return deepcopy(record) if record is not None else None

    def get_for_schedule(self, task_id: str, schedule_id: str) -> Optional[AgentTaskRecoveryScheduleDispatch]:
        record = self._by_schedule.get((task_id, schedule_id))
        return deepcopy(record) if record is not None else None

    def list_for_task(self, task_id: str) -> list:
        entries = self._by_task.get(task_id, [])
        return [deepcopy(entry) for entry in sorted(entries, key=lambda item: item.dispatched_at)]


class JsonAgentTaskRecoveryScheduleDispatchStore(AgentTaskRecoveryScheduleDispatchStore):
    """Persists AgentTaskRecoveryScheduleDispatch records to a JSON file,
    keyed by dispatch_id; the other lookups scan the (small) collection."""

    def __init__(self, path: str | Path):
        self.file = AtomicJsonFile(path, default_factory=dict)

    def save(self, record: AgentTaskRecoveryScheduleDispatch) -> AgentTaskRecoveryScheduleDispatch:
        records = self.file.read()
        records[record.dispatch_id] = record.to_dict()
        self.file.write(records)
        return deepcopy(record)

    def get(self, dispatch_id: str) -> Optional[AgentTaskRecoveryScheduleDispatch]:
        data = self.file.read().get(dispatch_id)
        return AgentTaskRecoveryScheduleDispatch.from_dict(data) if data is not None else None

    def get_for_schedule(self, task_id: str, schedule_id: str) -> Optional[AgentTaskRecoveryScheduleDispatch]:
        for data in self.file.read().values():
            if data.get("task_id") == task_id and data.get("schedule_id") == schedule_id:
                return AgentTaskRecoveryScheduleDispatch.from_dict(data)
        return None

    def list_for_task(self, task_id: str) -> list:
        matching = [
            AgentTaskRecoveryScheduleDispatch.from_dict(data)
            for data in self.file.read().values()
            if data.get("task_id") == task_id
        ]
        return sorted(matching, key=lambda item: item.dispatched_at)


class LLMAgentTaskRecoveryPreflightScheduleDispatchService:
    """The bridge from "eligible schedule" to "handed off to the existing
    task queue/dispatch mechanism" -- never a new dispatcher or queue
    system (Rule: "Do not invent a dispatcher or queue system"):
    dispatch() validates via Commit #2's own schedule validation service
    (reusing its full stale/invalidated/cancelled/window logic, nothing
    re-derived), then calls whatever real, existing queue/dispatch
    collaborator the caller supplied (e.g. backend.agent_task_queue.
    LLMAgentTaskQueueService.enqueue()) -- optional, duck-typed, the same
    "used only if given" shape this whole project's own services already
    follow, since a production deployment's own recovery-dispatch queue
    may well be a different existing mechanism than the plain "ready
    work" queue (which, unlike a failed task awaiting recovery, requires
    the task to already be READY).

    Never executes recovery (Rule): nothing here calls Commit #4(-of-
    agent_task_event_analytics)'s own execution service, or Commit #11(-of-
    agent_task_recovery_guardrails)'s own consumption service -- dispatch()
    only ever hands off a reference, it never runs the plan itself.

    Idempotent by (task_id, schedule_id) (Rule: "Prevent duplicate
    dispatch of the same schedule"): a schedule already dispatched
    returns its original record unchanged, and the queue/dispatch
    collaborator is never called a second time for it.
    """

    def __init__(
        self,
        validation_service: LLMAgentTaskRecoveryPreflightScheduleValidationService = None,
        scheduling_service: LLMAgentTaskRecoveryPreflightSchedulingService = None,
        queue_service=None,
        store: AgentTaskRecoveryScheduleDispatchStore = None,
    ):
        self._scheduling_service = (
            scheduling_service if scheduling_service is not None else LLMAgentTaskRecoveryPreflightSchedulingService()
        )
        self._validation_service = (
            validation_service
            if validation_service is not None
            else LLMAgentTaskRecoveryPreflightScheduleValidationService(scheduling_service=self._scheduling_service)
        )
        self._queue_service = queue_service
        self._store = store if store is not None else InMemoryAgentTaskRecoveryScheduleDispatchStore()

    def dispatch(self, task_id: str, schedule_id: str) -> AgentTaskRecoveryScheduleDispatch:
        """Validate, then dispatch, task_id's exact schedule_id exactly
        once. Idempotent: an already-dispatched schedule returns its
        original recorded outcome unchanged.

        Raises:
            InvalidAgentTaskRecoveryScheduleDispatchError: If task_id/
                schedule_id is not a non-empty string, Commit #2's own
                validate() reports the schedule not currently eligible,
                or the configured queue collaborator's own enqueue()
                raises
        """
        self._require_text(task_id, "task_id")
        self._require_text(schedule_id, "schedule_id")

        existing = self._store.get_for_schedule(task_id, schedule_id)
        if existing is not None:
            return existing

        validation = self._validation_service.validate(task_id, schedule_id)
        if not validation.valid:
            raise InvalidAgentTaskRecoveryScheduleDispatchError(
                f"schedule {schedule_id!r} is not currently eligible to dispatch: "
                + "; ".join(validation.blocking_reasons)
            )

        queue_reference = None
        if self._queue_service is not None:
            try:
                entry = self._queue_service.enqueue(task_id)
            except Exception as error:
                raise InvalidAgentTaskRecoveryScheduleDispatchError(
                    f"could not hand off schedule {schedule_id!r} to the queue: {error}"
                ) from error
            queue_reference = getattr(entry, "task_id", None) or str(entry)

        record = AgentTaskRecoveryScheduleDispatch(
            task_id=task_id, schedule_id=schedule_id, preflight_id=validation.preflight_id,
            dispatched_at=datetime.now(timezone.utc), status=DISPATCHED, queue_reference=queue_reference,
        )
        return self._store.save(record)

    def get(self, task_id: str, dispatch_id: str) -> Optional[AgentTaskRecoveryScheduleDispatch]:
        """task_id's dispatch record for its exact dispatch_id, or None
        if it does not exist or belongs to a different task_id.

        Raises:
            InvalidAgentTaskRecoveryScheduleDispatchError: If task_id or
                dispatch_id is not a non-empty string
        """
        self._require_text(task_id, "task_id")
        self._require_text(dispatch_id, "dispatch_id")
        record = self._store.get(dispatch_id)
        if record is None or record.task_id != task_id:
            return None
        return record

    def list(self, task_id: str) -> list:
        """Every dispatch ever recorded for task_id, oldest to newest."""
        self._require_text(task_id, "task_id")
        return self._store.list_for_task(task_id)

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryScheduleDispatchError(
                f"{field_name} is required and must be a non-empty string"
            )
