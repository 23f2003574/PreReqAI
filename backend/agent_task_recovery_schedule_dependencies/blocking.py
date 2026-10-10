from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

from backend.agent_task_recovery_scheduling import (
    LLMAgentTaskRecoveryPreflightScheduleExpirationService,
    LLMAgentTaskRecoveryPreflightSchedulingService,
    LLMAgentTaskRecoveryPreflightScheduleValidationService,
)
from backend.storage import AtomicJsonFile

from .service import LLMAgentTaskRecoveryPreflightScheduleDependencyService

# Named BLOCK_STATUS_* (never bare BLOCKED/UNBLOCKED) to avoid colliding
# with this package's own Commit #1 models.BLOCKED -- an unrelated
# dependency-gate STATE that happens to share the same string value but
# a completely different axis (a live dependency verdict, never a
# durable block record's own status).
BLOCK_STATUS_BLOCKED = "blocked"
BLOCK_STATUS_UNBLOCKED = "unblocked"
BLOCK_STATUSES = frozenset({BLOCK_STATUS_BLOCKED, BLOCK_STATUS_UNBLOCKED})


class InvalidAgentTaskRecoveryScheduleDependencyBlockingError(ValueError):
    """Raised when block()/unblock()/status() is given invalid
    arguments, or block()/unblock() is asked for a transition that is
    not currently legal (dependencies are already ready when block() is
    called; dependencies are still not ready, or the schedule is stale/
    expired/cancelled/unauthorized/otherwise invalid, when unblock() is
    called)."""


@dataclass(frozen=True)
class AgentTaskRecoveryScheduleDependencyBlock:
    """One immutable, append-only entry in one (task_id, schedule_id)'s
    own dependency-blocking transition history (Rule: "Preserve
    transition history") -- never updated or deleted once recorded, the
    same append-only discipline backend.agent_task_state_history.
    TaskTransitionRecord and this package's own Commit #2
    AgentTaskRecoveryScheduleDependencyObservation already establish.

    dependencies is exactly what the caller passed to block() (or,
    for an unblock() transition, carried forward unchanged from the
    block it clears) -- the caller's own account of which
    dependency_task_ids this transition is about. evidence is this
    exact transition's own independently-fetched Commit #1/#2
    dependency_result.blockers -- never trusted from the caller, always
    read fresh at transition time (Rule: "Preserve the dependency
    evidence and reason that caused the block"), empty for an unblock()
    transition (nothing left to report -- dependencies are ready).
    """

    task_id: str
    schedule_id: str
    preflight_id: Optional[str]
    status: str
    dependencies: tuple
    evidence: tuple
    reason: str
    occurred_at: datetime
    block_id: str = field(default_factory=lambda: str(uuid4()))

    def to_dict(self) -> dict:
        data = asdict(self)
        data["occurred_at"] = self.occurred_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "AgentTaskRecoveryScheduleDependencyBlock":
        payload = dict(data)
        value = payload.get("occurred_at")
        if isinstance(value, str):
            payload["occurred_at"] = datetime.fromisoformat(value)
        for key in ("dependencies", "evidence"):
            if key in payload and payload[key] is not None:
                payload[key] = tuple(payload[key])
        return cls(**payload)


@dataclass(frozen=True)
class AgentTaskRecoveryScheduleDependencyBlockingStatus:
    """status()/check()'s complete, read-only picture of one (task_id,
    schedule_id)'s current dependency-blocking standing -- never mutates
    anything (Rule: "No recovery execution or task-state mutation"),
    re-derived fresh on every call.

    ready/blockers are the shape backend.agent_task_recovery_scheduling.
    LLMAgentTaskRecoveryPreflightScheduleValidationService's own
    optional, duck-typed dependency_service hook already expects (Rule:
    "Feed blocking state into existing schedule validation/dispatch
    eligibility") -- ready is exactly `not currently_blocked`; blockers
    is non-empty exactly when currently_blocked, naming the durable
    block's own reason and evidence. Deliberately does NOT re-derive
    live dependency readiness here the way Commit #1/#2's own check()
    do: once explicitly blocked, a schedule stays blocked -- sticky,
    not auto-cleared by validate() -- until unblock() is explicitly
    called and succeeds (Rule: "Automatically determine whether an
    existing block CAN BE cleared" describes unblock()'s own
    precondition check, never an implicit clear during an ordinary
    read).

    can_unblock/unblock_blockers answer a different question: would
    calling unblock() right now actually succeed. True/empty whenever
    NOT currently_blocked (unblock() would just no-op). Otherwise
    reflects every reason unblock() would currently refuse: dependencies
    still not ready, or the schedule itself is stale/expired/cancelled/
    unauthorized/otherwise invalid (Rule: "Never unblock a schedule that
    is stale, expired, cancelled, unauthorized, or otherwise invalid").
    """

    task_id: str
    schedule_id: str
    ready: bool
    currently_blocked: bool
    blockers: tuple
    can_unblock: bool
    unblock_blockers: tuple
    current_record: Optional[AgentTaskRecoveryScheduleDependencyBlock]
    checked_at: datetime


class AgentTaskRecoveryScheduleDependencyBlockStore(ABC):
    """Append-only persistence for AgentTaskRecoveryScheduleDependencyBlock
    records -- the same save()/list_for_-- split this package's own
    Commit #2 AgentTaskRecoveryScheduleDependencyObservationStore already
    establishes for a comparable case. There is no update() or delete():
    a transition is never overwritten or removed once recorded."""

    @abstractmethod
    def save(self, record: AgentTaskRecoveryScheduleDependencyBlock) -> AgentTaskRecoveryScheduleDependencyBlock:
        ...

    @abstractmethod
    def list_for_schedule(self, task_id: str, schedule_id: str) -> list:
        ...

    @abstractmethod
    def list_for_task(self, task_id: str) -> list:
        ...


class InMemoryAgentTaskRecoveryScheduleDependencyBlockStore(AgentTaskRecoveryScheduleDependencyBlockStore):
    """Stores dependency-blocking transition records in memory, for
    development and testing."""

    def __init__(self):
        self._by_schedule: dict = {}

    def save(self, record: AgentTaskRecoveryScheduleDependencyBlock) -> AgentTaskRecoveryScheduleDependencyBlock:
        stored = deepcopy(record)
        self._by_schedule.setdefault((record.task_id, record.schedule_id), []).append(stored)
        return deepcopy(stored)

    def list_for_schedule(self, task_id: str, schedule_id: str) -> list:
        entries = self._by_schedule.get((task_id, schedule_id), [])
        return [deepcopy(entry) for entry in sorted(entries, key=lambda item: item.occurred_at)]

    def list_for_task(self, task_id: str) -> list:
        entries = [entry for (t, _), entries in self._by_schedule.items() if t == task_id for entry in entries]
        return [deepcopy(entry) for entry in sorted(entries, key=lambda item: item.occurred_at)]


class JsonAgentTaskRecoveryScheduleDependencyBlockStore(AgentTaskRecoveryScheduleDependencyBlockStore):
    """Persists dependency-blocking transition records to a JSON file,
    keyed by f"{task_id}::{schedule_id}"."""

    def __init__(self, path: str | Path):
        self.file = AtomicJsonFile(path, default_factory=dict)

    @staticmethod
    def _key(task_id: str, schedule_id: str) -> str:
        return f"{task_id}::{schedule_id}"

    def save(self, record: AgentTaskRecoveryScheduleDependencyBlock) -> AgentTaskRecoveryScheduleDependencyBlock:
        records = self.file.read()
        key = self._key(record.task_id, record.schedule_id)
        records.setdefault(key, []).append(record.to_dict())
        self.file.write(records)
        return deepcopy(record)

    def list_for_schedule(self, task_id: str, schedule_id: str) -> list:
        records = self.file.read()
        matching = [
            AgentTaskRecoveryScheduleDependencyBlock.from_dict(data)
            for data in records.get(self._key(task_id, schedule_id), [])
        ]
        return sorted(matching, key=lambda item: item.occurred_at)

    def list_for_task(self, task_id: str) -> list:
        records = self.file.read()
        prefix = f"{task_id}::"
        matching = [
            AgentTaskRecoveryScheduleDependencyBlock.from_dict(data)
            for key, entries in records.items() if key.startswith(prefix)
            for data in entries
        ]
        return sorted(matching, key=lambda item: item.occurred_at)


class LLMAgentTaskRecoveryPreflightScheduleDependencyBlockingService:
    """Durable, explicit BLOCKED/UNBLOCKED state for one Commit #1
    schedule -- never a second dependency resolver or queue framework
    (Rule: "Do not create another dependency or queue framework"):
    every dependency fact here comes straight from Commit #1's own gate
    or Commit #2's own reconciliation service (whichever is supplied as
    dependency_service -- both already expose the identical check()
    shape), and every non-dependency validity fact (cancelled/
    invalidated/revoked/policy-blocked/execution-window, stale/expired)
    comes straight from backend.agent_task_recovery_scheduling's own
    existing LLMAgentTaskRecoveryPreflightScheduleValidationService/
    LLMAgentTaskRecoveryPreflightScheduleExpirationService -- nothing
    here re-derives dependency traversal or schedule validity a second
    way.

    Deliberately sticky, unlike Commit #1/#2's own always-live check()
    (Rule): once block() succeeds, a schedule reads as blocked (see
    check()/status()) regardless of any LATER live dependency change,
    until unblock() is explicitly called and itself succeeds (Rule:
    "Automatically determine whether an existing block CAN BE cleared"
    -- unblock()'s own precondition check, not an implicit background
    clear). This is the intended contrast with Commit #2's reconciliation
    service: reconciliation continuously re-observes and reports live
    drift; blocking is a deliberate, durable circuit breaker a caller
    (an operator, or an automated sweep) explicitly sets and clears.

    block(task_id, schedule_id, dependencies, reason) only ever succeeds
    when Commit #1/#2's own dependency_service.check() currently reports
    NOT ready (Rule: "Block only when current dependency reconciliation
    says the schedule is not ready") -- a schedule whose dependencies
    are already satisfied cannot be blocked at all, raising instead.
    dependencies/reason are the caller's own account, preserved
    verbatim; evidence is this exact call's own independently-fetched
    dependency_result.blockers, never trusted from the caller (Rule:
    "Preserve the dependency evidence and reason that caused the
    block").

    unblock(task_id, schedule_id, reason=None) only ever succeeds when
    BOTH (Rule: "Never unblock a schedule that is stale, expired,
    cancelled, unauthorized, or otherwise invalid"):
      - the schedule is not stale/expired (Commit #9-of-agent_task_
        recovery_scheduling's own expiration_service.check(), when
        supplied) and not cancelled/invalidated/revoked/policy-blocked/
        outside its own execution window (that series' own Commit #2
        validation_service.validate() -- deliberately built WITHOUT its
        own optional dependency_service hook wired here, so this
        service's own dependency check below is the only dependency
        opinion consulted, never a second, differently-configured one);
      - AND dependency_service.check() currently reports ready (Rule:
        "Automatically determine whether an existing block can be
        cleared when dependencies become ready" -- unblock() re-checks
        live every call, it is never handed a caller-asserted verdict).
    Either failing raises, naming every reason.

    Idempotent (Rule: "make repeated block/unblock operations
    idempotent"): block() on an already-BLOCKED schedule, or unblock()
    on an already-UNBLOCKED (or never-blocked) one, is a pure no-op
    returning the current record (or None) completely unchanged -- no
    new history row, the same "already in the target state, nothing
    left to do" discipline Commit #1-of-agent_task_recovery_scheduling's
    own cancel() and that series' own Commit #9 expire() already
    establish. A genuine transition (none/UNBLOCKED -> BLOCKED,
    BLOCKED -> UNBLOCKED) always records exactly one new, permanent
    AgentTaskRecoveryScheduleDependencyBlock entry (Rule: "Preserve
    transition history").

    Never executes recovery or mutates task/schedule state (Rule): the
    only write anywhere in this class is this module's own block store
    -- nothing here ever calls Commit #1-of-agent_task_recovery_
    scheduling's own schedule()/cancel()/dispatch(), Commit #1-of-
    agent_task_lifecycle's own transition(), or anything from
    backend.agent_task_recovery_guardrails' own write paths.

    check() is the bridge (Rule: "Feed blocking state into existing
    schedule validation/dispatch eligibility") -- a thin, read-only
    alias for status(), whose own .ready/.blockers already match the
    exact shape backend.agent_task_recovery_scheduling.
    LLMAgentTaskRecoveryPreflightScheduleValidationService's own
    optional dependency_service hook expects. A caller wires THIS
    service (in place of, or chained after, Commit #1/#2's own) into
    that hook to make a durable block actually refuse dispatch.
    """

    def __init__(
        self,
        dependency_service=None,
        scheduling_service: LLMAgentTaskRecoveryPreflightSchedulingService = None,
        validation_service: LLMAgentTaskRecoveryPreflightScheduleValidationService = None,
        expiration_service: LLMAgentTaskRecoveryPreflightScheduleExpirationService = None,
        store: AgentTaskRecoveryScheduleDependencyBlockStore = None,
    ):
        """
        Args:
            dependency_service: Commit #1's gate or Commit #2's
                reconciliation service -- either already exposes the
                identical check(task_id, schedule_id) -> .ready/
                .blockers shape. Defaults to a fresh Commit #1
                LLMAgentTaskRecoveryPreflightScheduleDependencyService
                (no dependency_resolver of its own -- see that class's
                own docstring: with none configured it always reports
                ready, so block() would then always refuse; pass the
                real, wired instance for this service to ever do
                anything).
            scheduling_service: Defaults to a fresh
                LLMAgentTaskRecoveryPreflightSchedulingService; used
                only to build a default dependency_service/
                validation_service when neither is given.
            validation_service: Defaults to a fresh
                LLMAgentTaskRecoveryPreflightScheduleValidationService
                built over scheduling_service, WITHOUT its own
                dependency_service wired -- unblock() consults this
                exclusively for cancelled/invalidated/revoked/policy/
                window validity, never for dependency readiness (this
                class's own dependency_service already owns that).
            expiration_service: No default (mirrors Commit #1-of-
                agent_task_readiness's own planning_service -- a fresh
                instance could never see real schedules). When given,
                unblock() also refuses a stale/expired schedule; when
                omitted, that check is simply skipped.
            store: Defaults to a fresh
                InMemoryAgentTaskRecoveryScheduleDependencyBlockStore.
        """
        self._scheduling_service = (
            scheduling_service if scheduling_service is not None else LLMAgentTaskRecoveryPreflightSchedulingService()
        )
        self._dependency_service = (
            dependency_service
            if dependency_service is not None
            else LLMAgentTaskRecoveryPreflightScheduleDependencyService(scheduling_service=self._scheduling_service)
        )
        self._validation_service = (
            validation_service
            if validation_service is not None
            else LLMAgentTaskRecoveryPreflightScheduleValidationService(scheduling_service=self._scheduling_service)
        )
        self._expiration_service = expiration_service
        self._store = store if store is not None else InMemoryAgentTaskRecoveryScheduleDependencyBlockStore()

    def check(self, task_id: str, schedule_id: str) -> AgentTaskRecoveryScheduleDependencyBlockingStatus:
        """Read-only alias for status() -- the bridge this service
        exposes for backend.agent_task_recovery_scheduling.
        LLMAgentTaskRecoveryPreflightScheduleValidationService's own
        optional dependency_service hook (see this class's own
        docstring)."""
        return self.status(task_id, schedule_id)

    def status(self, task_id: str, schedule_id: str) -> AgentTaskRecoveryScheduleDependencyBlockingStatus:
        """task_id's exact schedule_id's current dependency-blocking
        standing, re-derived fresh every call. Never mutates anything.

        Raises:
            InvalidAgentTaskRecoveryScheduleDependencyBlockingError: If
                task_id or schedule_id is not a non-empty string
        """
        self._require_text(task_id, "task_id")
        self._require_text(schedule_id, "schedule_id")
        now = datetime.now(timezone.utc)

        current = self.get_latest(task_id, schedule_id)
        currently_blocked = current is not None and current.status == BLOCK_STATUS_BLOCKED

        if not currently_blocked:
            return AgentTaskRecoveryScheduleDependencyBlockingStatus(
                task_id=task_id, schedule_id=schedule_id, ready=True, currently_blocked=False, blockers=(),
                can_unblock=True, unblock_blockers=(), current_record=current, checked_at=now,
            )

        blockers = (f"schedule is durably blocked: {current.reason}",) + current.evidence
        unblock_blockers = self._unblock_blockers(task_id, schedule_id)
        return AgentTaskRecoveryScheduleDependencyBlockingStatus(
            task_id=task_id, schedule_id=schedule_id, ready=False, currently_blocked=True, blockers=blockers,
            can_unblock=not unblock_blockers, unblock_blockers=tuple(unblock_blockers),
            current_record=current, checked_at=now,
        )

    def block(
        self, task_id: str, schedule_id: str, dependencies, reason: str
    ) -> AgentTaskRecoveryScheduleDependencyBlock:
        """Durably block task_id's exact schedule_id, recording
        dependencies/reason plus this call's own live dependency
        evidence. Idempotent: an already-BLOCKED schedule is returned
        unchanged, no-op.

        Raises:
            InvalidAgentTaskRecoveryScheduleDependencyBlockingError: If
                task_id/schedule_id/reason is not a non-empty string,
                dependencies is not a non-empty sequence of non-empty
                strings, or the schedule's dependencies are currently
                ready (nothing to block)
        """
        self._require_text(task_id, "task_id")
        self._require_text(schedule_id, "schedule_id")
        self._require_text(reason, "reason")
        dependency_ids = self._require_dependencies(dependencies)

        current = self.get_latest(task_id, schedule_id)
        if current is not None and current.status == BLOCK_STATUS_BLOCKED:
            return current

        result = self._dependency_service.check(task_id, schedule_id)
        if result.ready:
            raise InvalidAgentTaskRecoveryScheduleDependencyBlockingError(
                f"schedule {schedule_id!r} cannot be blocked: dependencies are currently ready"
            )

        record = AgentTaskRecoveryScheduleDependencyBlock(
            task_id=task_id, schedule_id=schedule_id, preflight_id=getattr(result, "preflight_id", None),
            status=BLOCK_STATUS_BLOCKED, dependencies=dependency_ids, evidence=tuple(result.blockers),
            reason=reason, occurred_at=datetime.now(timezone.utc),
        )
        return self._store.save(record)

    def unblock(
        self, task_id: str, schedule_id: str, reason: str = None
    ) -> AgentTaskRecoveryScheduleDependencyBlock:
        """Durably unblock task_id's exact schedule_id, if currently
        eligible. Idempotent: a schedule that is not currently blocked
        (never blocked, or already UNBLOCKED) is returned unchanged
        (None if it was never blocked at all), no-op.

        Raises:
            InvalidAgentTaskRecoveryScheduleDependencyBlockingError: If
                task_id/schedule_id is not a non-empty string, reason is
                given and is not a string, or the schedule is not
                currently eligible to be unblocked (dependencies still
                not ready, or the schedule itself is stale/expired/
                cancelled/unauthorized/otherwise invalid)
        """
        self._require_text(task_id, "task_id")
        self._require_text(schedule_id, "schedule_id")
        if reason is not None and not isinstance(reason, str):
            raise InvalidAgentTaskRecoveryScheduleDependencyBlockingError("reason must be a string when given")

        current = self.get_latest(task_id, schedule_id)
        if current is None or current.status == BLOCK_STATUS_UNBLOCKED:
            return current

        blockers = self._unblock_blockers(task_id, schedule_id)
        if blockers:
            raise InvalidAgentTaskRecoveryScheduleDependencyBlockingError(
                f"schedule {schedule_id!r} cannot be unblocked: " + "; ".join(blockers)
            )

        result = self._dependency_service.check(task_id, schedule_id)
        record = AgentTaskRecoveryScheduleDependencyBlock(
            task_id=task_id, schedule_id=schedule_id, preflight_id=getattr(result, "preflight_id", None),
            status=BLOCK_STATUS_UNBLOCKED, dependencies=current.dependencies, evidence=(),
            reason=reason if reason is not None else "dependencies are now ready", occurred_at=datetime.now(timezone.utc),
        )
        return self._store.save(record)

    def get_history(self, task_id: str, schedule_id: str) -> list:
        """Every blocking transition ever recorded for task_id's exact
        schedule_id, oldest first -- never mutated or trimmed (Rule:
        "Preserve transition history")."""
        self._require_text(task_id, "task_id")
        self._require_text(schedule_id, "schedule_id")
        return self._store.list_for_schedule(task_id, schedule_id)

    def get_latest(self, task_id: str, schedule_id: str):
        """The most recent blocking transition for task_id's exact
        schedule_id, or None if it has never been blocked."""
        history = self.get_history(task_id, schedule_id)
        return history[-1] if history else None

    def _unblock_blockers(self, task_id: str, schedule_id: str) -> list:
        blockers: list = []

        validation = self._validation_service.validate(task_id, schedule_id)
        if not validation.valid:
            blockers.extend(validation.blocking_reasons)

        if self._expiration_service is not None:
            expiration = self._expiration_service.check(task_id, schedule_id)
            if expiration.expired:
                blockers.append(expiration.reason)

        result = self._dependency_service.check(task_id, schedule_id)
        if not result.ready:
            if result.blockers:
                blockers.extend(f"dependencies are still not ready: {reason}" for reason in result.blockers)
            else:
                blockers.append("dependencies are still not ready")

        return blockers

    @staticmethod
    def _require_dependencies(dependencies) -> tuple:
        if not isinstance(dependencies, (list, tuple)) or not dependencies:
            raise InvalidAgentTaskRecoveryScheduleDependencyBlockingError(
                "dependencies is required and must be a non-empty list/tuple of non-empty strings"
            )
        for dependency_task_id in dependencies:
            if not dependency_task_id or not isinstance(dependency_task_id, str):
                raise InvalidAgentTaskRecoveryScheduleDependencyBlockingError(
                    "every entry in dependencies must be a non-empty string"
                )
        return tuple(dependencies)

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryScheduleDependencyBlockingError(
                f"{field_name} is required and must be a non-empty string"
            )
