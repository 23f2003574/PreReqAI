from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

from backend.agent_task_recovery_scheduling import LLMAgentTaskRecoveryPreflightSchedulingService
from backend.storage import AtomicJsonFile

from .escalation import LLMAgentTaskRecoveryPreflightScheduleDependencyEscalationService
from .timeout import NOT_APPLICABLE as TIMEOUT_NOT_APPLICABLE
from .timeout import NOT_WAITING
from .wake import LLMAgentTaskRecoveryPreflightScheduleDependencyWakeService

RESOLUTION_WOKEN = "woken"
RESOLUTION_TERMINAL = "terminal"
RESOLUTION_OUTCOMES = frozenset({RESOLUTION_WOKEN, RESOLUTION_TERMINAL})


class InvalidAgentTaskRecoveryScheduleEscalationResolutionError(ValueError):
    """Raised when check()/resolve() is given invalid arguments, names a
    schedule that does not exist for task_id, or resolve() is asked to
    resolve a schedule that was never escalated in the first place
    (Commit #7's own escalate() must have succeeded for it at least
    once)."""


@dataclass(frozen=True)
class AgentTaskRecoveryScheduleEscalationResolutionResult:
    """check()'s read-only, explainable verdict, and resolve()'s own
    return value once it has acted.

    escalated is False only when Commit #7's own get_history() is
    completely empty for this exact (task_id, schedule_id) -- there is
    nothing here to resolve at all.

    can_resolve/outcome answer "would resolve() act, and how, right
    now": outcome is RESOLUTION_WOKEN when Commit #2's own live
    reconciliation shows the original dependency block actually cleared
    (Rule: "Resolve escalation only when the original blocking
    condition is actually cleared"), RESOLUTION_TERMINAL when the
    schedule itself has independently become stale/expired/cancelled/
    invalid (Rule: "resolve into the appropriate terminal scheduling
    state instead of making it actionable" -- Commit #6's own
    NOT_APPLICABLE already IS that terminal determination, reused
    verbatim), and None while genuinely still blocked (Rule: "If
    dependencies remain blocked, preserve escalation" -- can_resolve is
    False here, nothing to act on yet).

    already_resolved is True once a resolve() call has already recorded
    an outcome for this exact escalation -- can_resolve is always False
    once already_resolved is True (Rule: "Make resolution idempotent").
    """

    task_id: str
    schedule_id: str
    preflight_id: Optional[str]
    escalated: bool
    already_resolved: bool
    can_resolve: bool
    outcome: Optional[str]
    dependency_evidence: tuple
    reason: str
    checked_at: datetime


@dataclass(frozen=True)
class AgentTaskRecoveryScheduleEscalationResolution:
    """One immutable, append-only entry recording that task_id's exact
    schedule_id's escalation was resolved -- never updated or deleted
    once recorded (Rule: "Preserve escalation and dependency history"),
    the same append-only discipline this package's own Commit #2/#3/#5/
    #7 already establish. Never itself a second copy of Commit #7's own
    escalation record -- this is purely a marker that THAT escalation
    has now been acted on, and how."""

    task_id: str
    schedule_id: str
    preflight_id: Optional[str]
    outcome: str
    reason: str
    resolved_at: datetime
    resolution_id: str = field(default_factory=lambda: str(uuid4()))

    def to_dict(self) -> dict:
        data = asdict(self)
        data["resolved_at"] = self.resolved_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "AgentTaskRecoveryScheduleEscalationResolution":
        payload = dict(data)
        value = payload.get("resolved_at")
        if isinstance(value, str):
            payload["resolved_at"] = datetime.fromisoformat(value)
        return cls(**payload)


class AgentTaskRecoveryScheduleEscalationResolutionStore(ABC):
    """Append-only persistence for AgentTaskRecoveryScheduleEscalationResolution
    records -- the same save()/list_for_-- split this package's own
    Commit #2/#3/#5/#7 stores already establish. There is no update() or
    delete()."""

    @abstractmethod
    def save(
        self, record: AgentTaskRecoveryScheduleEscalationResolution
    ) -> AgentTaskRecoveryScheduleEscalationResolution:
        ...

    @abstractmethod
    def list_for_schedule(self, task_id: str, schedule_id: str) -> list:
        ...

    @abstractmethod
    def list_for_task(self, task_id: str) -> list:
        ...


class InMemoryAgentTaskRecoveryScheduleEscalationResolutionStore(AgentTaskRecoveryScheduleEscalationResolutionStore):
    """Stores escalation resolutions in memory, for development and
    testing."""

    def __init__(self):
        self._by_schedule: dict = {}

    def save(
        self, record: AgentTaskRecoveryScheduleEscalationResolution
    ) -> AgentTaskRecoveryScheduleEscalationResolution:
        stored = deepcopy(record)
        self._by_schedule.setdefault((record.task_id, record.schedule_id), []).append(stored)
        return deepcopy(stored)

    def list_for_schedule(self, task_id: str, schedule_id: str) -> list:
        entries = self._by_schedule.get((task_id, schedule_id), [])
        return [deepcopy(entry) for entry in sorted(entries, key=lambda item: item.resolved_at)]

    def list_for_task(self, task_id: str) -> list:
        entries = [entry for (t, _), entries in self._by_schedule.items() if t == task_id for entry in entries]
        return [deepcopy(entry) for entry in sorted(entries, key=lambda item: item.resolved_at)]


class JsonAgentTaskRecoveryScheduleEscalationResolutionStore(AgentTaskRecoveryScheduleEscalationResolutionStore):
    """Persists escalation resolutions to a JSON file, keyed by
    f"{task_id}::{schedule_id}"."""

    def __init__(self, path: str | Path):
        self.file = AtomicJsonFile(path, default_factory=dict)

    @staticmethod
    def _key(task_id: str, schedule_id: str) -> str:
        return f"{task_id}::{schedule_id}"

    def save(
        self, record: AgentTaskRecoveryScheduleEscalationResolution
    ) -> AgentTaskRecoveryScheduleEscalationResolution:
        records = self.file.read()
        key = self._key(record.task_id, record.schedule_id)
        records.setdefault(key, []).append(record.to_dict())
        self.file.write(records)
        return deepcopy(record)

    def list_for_schedule(self, task_id: str, schedule_id: str) -> list:
        records = self.file.read()
        matching = [
            AgentTaskRecoveryScheduleEscalationResolution.from_dict(data)
            for data in records.get(self._key(task_id, schedule_id), [])
        ]
        return sorted(matching, key=lambda item: item.resolved_at)

    def list_for_task(self, task_id: str) -> list:
        records = self.file.read()
        prefix = f"{task_id}::"
        matching = [
            AgentTaskRecoveryScheduleEscalationResolution.from_dict(data)
            for key, entries in records.items() if key.startswith(prefix)
            for data in entries
        ]
        return sorted(matching, key=lambda item: item.resolved_at)


class LLMAgentTaskRecoveryPreflightScheduleDependencyEscalationResolutionService:
    """Closes Commit #7's own escalation loop -- never a second
    escalation/state-machine framework (Rule: "Do not create another
    escalation/state-machine framework"): every fact here comes from an
    existing collaborator, and the only write anywhere in this class
    (besides its own small append-only resolution-marker store) is
    Commit #5's own wake_service.wake_schedule() -- reused verbatim,
    never reimplemented (Rule: "Reuse existing wake-up/reconciliation
    transitions rather than duplicating them").

    check() reconciles before ever deciding anything (Rule: "Reconcile
    current dependencies before resolving"): when a reconciliation_service
    is supplied, its own reconcile() is called directly first, so the
    escalation_service's own subsequent assess() (which itself already
    re-checks live through Commit #6's own timeout check()) is never
    answering from anything but current-moment dependency state.

    Three, and only three, outcomes (Rule: "Resolve escalation only
    when the original blocking condition is actually cleared" / "If
    dependencies remain blocked, preserve escalation" / "resolve into
    the appropriate terminal scheduling state instead of making it
    actionable"):
      - still blocked (can_resolve=False, outcome=None): Commit #7's
        own escalation record is left completely untouched, nothing is
        written here either -- "preserve escalation" holds by
        construction, not by any special-casing.
      - dependencies now ready (outcome=RESOLUTION_WOKEN): resolve()
        calls Commit #5's own wake_service.wake_schedule() -- which
        itself only ever cancels+reschedules to execute_at=None,
        handing the schedule back to Commit #2-of-agent_task_recovery_
        scheduling's own ordinary validate()/dispatch() path (Rule: "do
        not directly dispatch or execute recovery" -- nothing here, or
        in wake_schedule() itself, ever calls dispatch()).
      - schedule itself now terminal (outcome=RESOLUTION_TERMINAL):
        Commit #6's own NOT_APPLICABLE (cancelled/unauthorized/
        dispatched/already-Commit-#9-expired -- covers a stale
        preflight's own resulting INVALIDATED effective status too) is
        reused as-is; resolve() never calls wake_schedule() here, since
        making an already-terminal schedule "actionable" is exactly
        what Rule forbids -- only the resolution marker is recorded.

    Idempotent (Rule: "Make resolution idempotent"): once a resolution
    has been recorded for this exact (task_id, schedule_id), check()
    reports already_resolved=True and resolve() is a pure no-op
    returning that same view, forever -- there is no un-resolve.

    Never bypasses authorization, capacity, policy, or guard checks
    (Rule): the ONE write that touches the schedule itself is Commit
    #5's own wake_schedule(), which already enforces every one of those
    through its own existing collaborators; nothing here adds, removes,
    or shortcuts any of them.
    """

    def __init__(
        self,
        escalation_service: LLMAgentTaskRecoveryPreflightScheduleDependencyEscalationService = None,
        wake_service: LLMAgentTaskRecoveryPreflightScheduleDependencyWakeService = None,
        reconciliation_service=None,
        scheduling_service: LLMAgentTaskRecoveryPreflightSchedulingService = None,
        store: AgentTaskRecoveryScheduleEscalationResolutionStore = None,
    ):
        """
        Args:
            escalation_service: Commit #7's own escalation service --
                the sole source of "was this ever escalated" (its own
                get_history()) and of the live timeout/terminal
                determination (its own assess()). Defaults to a fresh
                LLMAgentTaskRecoveryPreflightScheduleDependencyEscalationService
                built over scheduling_service (no timeout_service of
                its own wired to real dependency data -- nothing would
                ever be found escalated; pass the real, wired instance
                for this service to ever do anything).
            wake_service: Commit #5's own wake service -- the sole
                mechanism used to return a schedule to the existing
                validation path once its dependency block clears.
                Defaults to a fresh
                LLMAgentTaskRecoveryPreflightScheduleDependencyWakeService
                built over scheduling_service.
            reconciliation_service: No default. When given, check()
                calls its own reconcile(task_id, schedule_id) directly
                before consulting escalation_service.assess(), an
                explicit, unconditional "reconcile before resolving"
                step (Rule) regardless of how escalation_service's own
                internal collaborators happen to be wired.
            scheduling_service: Defaults to a fresh
                LLMAgentTaskRecoveryPreflightSchedulingService; used to
                build defaults and to look the schedule up.
            store: Defaults to a fresh
                InMemoryAgentTaskRecoveryScheduleEscalationResolutionStore.
        """
        self._scheduling_service = (
            scheduling_service if scheduling_service is not None else LLMAgentTaskRecoveryPreflightSchedulingService()
        )
        self._escalation_service = (
            escalation_service
            if escalation_service is not None
            else LLMAgentTaskRecoveryPreflightScheduleDependencyEscalationService(
                scheduling_service=self._scheduling_service
            )
        )
        self._wake_service = (
            wake_service
            if wake_service is not None
            else LLMAgentTaskRecoveryPreflightScheduleDependencyWakeService(scheduling_service=self._scheduling_service)
        )
        self._reconciliation_service = reconciliation_service
        self._store = store if store is not None else InMemoryAgentTaskRecoveryScheduleEscalationResolutionStore()

    def check(
        self, task_id: str, schedule_id: str, now: Optional[datetime] = None
    ) -> AgentTaskRecoveryScheduleEscalationResolutionResult:
        """Read-only escalation-resolution verdict for task_id's exact
        schedule_id, re-evaluated fresh every call.

        Raises:
            InvalidAgentTaskRecoveryScheduleEscalationResolutionError:
                If task_id/schedule_id is not a non-empty string, now is
                given and is not a datetime, or schedule_id names no
                recorded schedule for task_id
        """
        self._require_text(task_id, "task_id")
        self._require_text(schedule_id, "schedule_id")
        now = self._resolve_now(now)

        schedule = self._scheduling_service.get(task_id, schedule_id)
        if schedule is None:
            raise InvalidAgentTaskRecoveryScheduleEscalationResolutionError(
                f"no schedule {schedule_id!r} is recorded for task_id {task_id!r}"
            )

        escalation_history = self._escalation_service.get_history(task_id, schedule_id)
        if not escalation_history:
            return self._result(
                task_id, schedule, False, False, False, None, (), "schedule was never escalated", now
            )

        resolution_history = self.get_history(task_id, schedule_id)
        if resolution_history:
            latest = resolution_history[-1]
            return self._result(
                task_id, schedule, True, True, False, latest.outcome,
                (), f"escalation already resolved as {latest.outcome!r}", now,
            )

        if self._reconciliation_service is not None:
            self._reconciliation_service.reconcile(task_id, schedule_id)

        assessment = self._escalation_service.assess(task_id, schedule_id, now=now)

        if assessment.timeout_state == TIMEOUT_NOT_APPLICABLE:
            return self._result(
                task_id, schedule, True, False, True, RESOLUTION_TERMINAL,
                assessment.dependency_evidence, f"schedule is already terminal: {assessment.reason}", now,
            )

        if assessment.timeout_state == NOT_WAITING:
            return self._result(
                task_id, schedule, True, False, True, RESOLUTION_WOKEN,
                (), "dependencies are now ready", now,
            )

        return self._result(
            task_id, schedule, True, False, False, None,
            assessment.dependency_evidence, f"dependencies are still not ready: {assessment.reason}", now,
        )

    def resolve(
        self, task_id: str, schedule_id: str, now: Optional[datetime] = None
    ) -> AgentTaskRecoveryScheduleEscalationResolutionResult:
        """Resolve task_id's exact schedule_id's escalation, if it is
        currently resolvable. Idempotent: an already-resolved escalation
        is returned unchanged, no-op; a still-blocked one is returned
        unchanged too (Rule: "preserve escalation"), also without
        raising.

        Raises:
            InvalidAgentTaskRecoveryScheduleEscalationResolutionError:
                If task_id/schedule_id is not a non-empty string, now is
                given and is not a datetime, schedule_id names no
                recorded schedule for task_id, or the schedule was never
                escalated in the first place
        """
        now = self._resolve_now(now)
        result = self.check(task_id, schedule_id, now=now)

        if not result.escalated:
            raise InvalidAgentTaskRecoveryScheduleEscalationResolutionError(
                f"schedule {schedule_id!r} was never escalated; nothing to resolve"
            )
        if result.already_resolved or not result.can_resolve:
            return result

        if result.outcome == RESOLUTION_WOKEN:
            self._wake_service.wake_schedule(task_id, schedule_id, now=now)

        record = AgentTaskRecoveryScheduleEscalationResolution(
            task_id=task_id, schedule_id=schedule_id, preflight_id=result.preflight_id,
            outcome=result.outcome, reason=result.reason, resolved_at=now,
        )
        self._store.save(record)

        return self.check(task_id, schedule_id, now=now)

    def get_history(self, task_id: str, schedule_id: str) -> list:
        """Every resolution ever recorded for task_id's exact
        schedule_id, oldest first -- never mutated or trimmed."""
        self._require_text(task_id, "task_id")
        self._require_text(schedule_id, "schedule_id")
        return self._store.list_for_schedule(task_id, schedule_id)

    @staticmethod
    def _result(task_id, schedule, escalated, already_resolved, can_resolve, outcome, evidence, reason, now):
        return AgentTaskRecoveryScheduleEscalationResolutionResult(
            task_id=task_id, schedule_id=schedule.schedule_id, preflight_id=schedule.preflight_id,
            escalated=escalated, already_resolved=already_resolved, can_resolve=can_resolve, outcome=outcome,
            dependency_evidence=tuple(evidence), reason=reason, checked_at=now,
        )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryScheduleEscalationResolutionError(
                f"{field_name} is required and must be a non-empty string"
            )

    @staticmethod
    def _resolve_now(now) -> datetime:
        if now is None:
            return datetime.now(timezone.utc)
        if not isinstance(now, datetime):
            raise InvalidAgentTaskRecoveryScheduleEscalationResolutionError("now must be a datetime when given")
        return now
