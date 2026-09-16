from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

from backend.agent_task_events import DEPENDENCY_ADDED, DEPENDENCY_REMOVED, LLMAgentTaskEventQueryService
from backend.agent_task_recovery_scheduling import (
    SCHEDULED,
    LLMAgentTaskRecoveryPreflightSchedulingService,
    LLMAgentTaskRecoveryPreflightScheduleValidationService,
)
from backend.storage import AtomicJsonFile

from .blocking import BLOCK_STATUS_BLOCKED
from .reconciliation import LLMAgentTaskRecoveryPreflightScheduleDependencyReconciliationService

_WINDOW_NOT_REACHED_MARKER = "execution window has not been reached"


class InvalidAgentTaskRecoveryScheduleDependencyWakeError(ValueError):
    """Raised when wake()/wake_schedule() is given invalid arguments, or
    wake_schedule() names a schedule_id that is not recorded for
    task_id."""


@dataclass(frozen=True)
class AgentTaskRecoveryScheduleWakeOutcome:
    """wake_schedule()'s own return value, and one entry in wake()'s own
    outcomes tuple -- reported for EVERY schedule considered, whether it
    was actually woken or preserved (Rule: "Preserve schedules that
    remain blocked" -- a preserved schedule is reported here, never
    silently dropped).

    woken is True in three cases, all distinguishable via already_awake/
    schedule_id vs previous_schedule_id:
      - a genuine wake happened: schedule_id is a NEW record (Commit #1-
        of-agent_task_recovery_scheduling's own cancel()+schedule(),
        execute_at=None), previous_schedule_id names the one it
        superseded, already_awake is False.
      - the schedule was already immediately actionable (Rule: "Avoid
        duplicate wake-ups"): schedule_id == previous_schedule_id,
        already_awake is True, nothing was written.
    woken is False when dependencies are still not ready, or the
    schedule is cancelled/invalidated/unauthorized/stale/expired (Rule:
    "Never bypass freshness, expiration, authorization, capacity, or
    policy validation") -- schedule_id == previous_schedule_id, reason
    names exactly why.

    dependency_evidence is this exact call's own Commit #2 reconciliation
    observation.blockers (empty once ready).
    """

    task_id: str
    schedule_id: str
    previous_schedule_id: str
    preflight_id: str
    woken: bool
    already_awake: bool
    reason: str
    dependency_evidence: tuple
    checked_at: datetime


@dataclass(frozen=True)
class AgentTaskRecoveryScheduleWakeResult:
    """wake()'s own complete report of one wake pass over every one of
    task_id's own currently-waiting schedules (Rule: "Find schedules
    currently waiting on the affected dependency").

    triggering_event_id is the most recent Commit #4-of-agent_task_events
    DEPENDENCY_ADDED/DEPENDENCY_REMOVED event recorded for task_id, when
    an event_query_service was supplied and at least one such event
    exists -- consumed purely as audit-trail correlation evidence (Rule:
    "consume/reuse existing task events ... rather than creating another
    event mechanism"), never as the gating signal for which schedules
    actually wake (Commit #2's own live reconciliation always is;
    events can be stale, missing, or -- since nothing in this repository
    currently emits them yet -- simply absent).
    """

    task_id: str
    dependency_id: Optional[str]
    outcomes: tuple
    triggering_event_id: Optional[str]
    woken_at: datetime

    @property
    def woken(self) -> tuple:
        return tuple(outcome for outcome in self.outcomes if outcome.woken and not outcome.already_awake)

    @property
    def preserved(self) -> tuple:
        return tuple(outcome for outcome in self.outcomes if not outcome.woken)


@dataclass(frozen=True)
class AgentTaskRecoveryScheduleWakeRecord:
    """One immutable, append-only entry in the durable wake history
    (Rule: "preserve wake history") -- recorded ONLY for a genuine wake
    transition (never for a preserved-blocked outcome, an already-awake
    no-op, or a refusal -- the same "record only an actual change"
    discipline this package's own Commit #3 blocking service and
    backend.agent_task_recovery_scheduling's own cancel()/expire()
    already establish)."""

    task_id: str
    schedule_id: str
    previous_schedule_id: str
    preflight_id: str
    dependency_id: Optional[str]
    reason: str
    triggering_event_id: Optional[str]
    woken_at: datetime
    wake_id: str = field(default_factory=lambda: str(uuid4()))

    def to_dict(self) -> dict:
        data = asdict(self)
        data["woken_at"] = self.woken_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "AgentTaskRecoveryScheduleWakeRecord":
        payload = dict(data)
        value = payload.get("woken_at")
        if isinstance(value, str):
            payload["woken_at"] = datetime.fromisoformat(value)
        return cls(**payload)


class AgentTaskRecoveryScheduleWakeStore(ABC):
    """Append-only persistence for AgentTaskRecoveryScheduleWakeRecord
    entries -- the same save()/list_for_-- split this package's own
    Commit #2/#3 stores already establish. There is no update() or
    delete()."""

    @abstractmethod
    def save(self, record: AgentTaskRecoveryScheduleWakeRecord) -> AgentTaskRecoveryScheduleWakeRecord:
        ...

    @abstractmethod
    def list_for_task(self, task_id: str) -> list:
        ...


class InMemoryAgentTaskRecoveryScheduleWakeStore(AgentTaskRecoveryScheduleWakeStore):
    """Stores wake records in memory, for development and testing."""

    def __init__(self):
        self._by_task: dict = {}

    def save(self, record: AgentTaskRecoveryScheduleWakeRecord) -> AgentTaskRecoveryScheduleWakeRecord:
        stored = deepcopy(record)
        self._by_task.setdefault(record.task_id, []).append(stored)
        return deepcopy(stored)

    def list_for_task(self, task_id: str) -> list:
        entries = self._by_task.get(task_id, [])
        return [deepcopy(entry) for entry in sorted(entries, key=lambda item: item.woken_at)]


class JsonAgentTaskRecoveryScheduleWakeStore(AgentTaskRecoveryScheduleWakeStore):
    """Persists wake records to a JSON file, keyed by task_id."""

    def __init__(self, path: str | Path):
        self.file = AtomicJsonFile(path, default_factory=dict)

    def save(self, record: AgentTaskRecoveryScheduleWakeRecord) -> AgentTaskRecoveryScheduleWakeRecord:
        records = self.file.read()
        records.setdefault(record.task_id, []).append(record.to_dict())
        self.file.write(records)
        return deepcopy(record)

    def list_for_task(self, task_id: str) -> list:
        records = self.file.read()
        matching = [AgentTaskRecoveryScheduleWakeRecord.from_dict(data) for data in records.get(task_id, [])]
        return sorted(matching, key=lambda item: item.woken_at)


class LLMAgentTaskRecoveryPreflightScheduleDependencyWakeService:
    """Brings a schedule this package's own Commit #4 wait service (or
    Commit #3 blocking service) deferred back into Commit #1-of-
    agent_task_recovery_scheduling's own ordinary actionable/
    dispatchable state, the instant its dependencies actually resolve --
    never a second event bus or scheduler (Rule: "Do not invent a new
    event bus or scheduler"): the ONLY writes anywhere in this class are
    that series' own already-idempotent cancel()/schedule() (Rule: "Move
    a schedule back into the repository's existing actionable/
    dispatchable state") and this module's own append-only wake-history
    store -- nothing here ever calls anything from backend.
    agent_task_event_analytics' own execution service or Commit #11-of-
    agent_task_recovery_guardrails' own consumption service (Rule: "do
    not execute recovery"). A genuine wake never calls this package's
    own Commit #3 blocking_service.unblock() either: that method's own
    precondition requires the schedule ALREADY be within its execution
    window, never true yet for a schedule this class is about to bring
    back to actionable -- and there is nothing to clear, since
    cancel()+schedule() always creates a brand-new schedule_id that was
    never blocked at all (see _wake_one()'s own comment for the full
    reasoning). Commit #3's own block record for the now-superseded
    original schedule_id is simply left exactly where it is, inert,
    permanently part of that series' own history.

    Reconciles before ever waking anything (Rule: "Reconcile dependency
    state before waking anything"): every candidate schedule's own
    readiness is decided by a real Commit #2 reconciliation_service.
    reconcile() call -- never a cached or caller-asserted verdict.

    Finds waiting schedules, and attributes them to a specific
    dependency_id, through Commit #3's own durable block record when one
    currently stands (its own `dependencies` is exactly the evidence
    recorded at block() time -- see _waiting_state()'s own docstring),
    falling back to "deferred to a future execute_at" (Commit #4's own
    wait service) when no blocking_service is configured at all -- a
    schedule found only that second way has no reliable per-dependency
    attribution, so a dependency_id filter never excludes it rather than
    risk silently dropping a genuine candidate (Rule: "Find schedules
    currently waiting on the affected dependency" / "Preserve schedules
    that remain blocked").

    Never bypasses an existing validity boundary (Rule: "Never bypass
    freshness, expiration, authorization, capacity, or policy
    validation"): before waking, every candidate is re-checked through
    Commit #2-of-agent_task_recovery_scheduling's own validation_service.
    validate() (which itself already reuses that series' own freshness/
    authorization/policy chain) -- with the one, deliberate exception of
    that same check's own "execution window has not been reached yet"
    reason, since bringing a still-deferred schedule back to immediately
    actionable is this class's entire purpose, and Commit #9's own
    expiration_service.check(), when supplied. Any OTHER blocking reason
    (cancelled, invalidated, revoked, policy-blocked, stale/expired)
    still refuses the wake outright. Capacity is never consulted here at
    all: this class never dispatches anything, so a woken schedule is
    merely eligible again for the SAME existing dispatch path capacity
    limits already gate -- Rule "do not execute recovery" already rules
    out this class calling dispatch() itself.

    Idempotent, duplicate-free (Rule: "Avoid duplicate wake-ups...
    Make repeated calls idempotent"): a schedule already immediately
    actionable (execute_at is None, or already <= now) is reported
    already_awake=True and left completely untouched -- no cancel(), no
    schedule(), no new wake-history row. Calling wake()/wake_schedule()
    again after a genuine wake already happened finds exactly this state
    and is a pure no-op the second time.

    Consumes existing task events rather than inventing a signal of its
    own (Rule): when an event_query_service is supplied, wake() reads
    backend.agent_task_events' own DEPENDENCY_ADDED/DEPENDENCY_REMOVED
    KNOWN_EVENT_TYPES for task_id purely as audit-trail correlation
    evidence attached to the result (Rule: "consume/reuse them rather
    than creating another event mechanism") -- never as the gating
    signal for readiness, which Commit #2's own live reconciliation
    always remains.
    """

    def __init__(
        self,
        reconciliation_service: LLMAgentTaskRecoveryPreflightScheduleDependencyReconciliationService = None,
        scheduling_service: LLMAgentTaskRecoveryPreflightSchedulingService = None,
        validation_service: LLMAgentTaskRecoveryPreflightScheduleValidationService = None,
        expiration_service=None,
        blocking_service=None,
        event_query_service: LLMAgentTaskEventQueryService = None,
        store: AgentTaskRecoveryScheduleWakeStore = None,
    ):
        """
        Args:
            reconciliation_service: Commit #2's own reconciliation
                service -- the sole source of dependency readiness here
                (Rule: "Reconcile dependency state before waking
                anything"). Defaults to a fresh instance built over
                scheduling_service (no dependency_resolver of its own --
                always reports ready, so wake() would then find nothing
                ever blocked; pass the real, wired instance for this
                service to ever do anything).
            scheduling_service: Defaults to a fresh
                LLMAgentTaskRecoveryPreflightSchedulingService; used to
                build defaults and for every schedule read/write.
            validation_service: Defaults to a fresh
                LLMAgentTaskRecoveryPreflightScheduleValidationService
                built over scheduling_service, WITHOUT its own
                dependency_service wired -- this class's own
                reconciliation_service already owns that opinion.
            expiration_service: No default (mirrors this package's own
                Commit #3/#4 -- a fresh instance could never see real
                schedules). When given, waking also refuses a stale/
                expired schedule; when omitted, that check is skipped.
            blocking_service: No default. When given, its own durable
                block records (dependencies recorded at block() time)
                are used to find waiting schedules and attribute them to
                a specific dependency_id (see _waiting_state()); its own
                unblock() is never called (see this class's own
                docstring for why).
            event_query_service: No default. When given, wake() reads
                its own query() for the most recent DEPENDENCY_ADDED/
                DEPENDENCY_REMOVED event recorded for task_id, purely as
                correlation evidence on the returned result.
            store: Defaults to a fresh
                InMemoryAgentTaskRecoveryScheduleWakeStore.
        """
        self._scheduling_service = (
            scheduling_service if scheduling_service is not None else LLMAgentTaskRecoveryPreflightSchedulingService()
        )
        self._reconciliation_service = (
            reconciliation_service
            if reconciliation_service is not None
            else LLMAgentTaskRecoveryPreflightScheduleDependencyReconciliationService(
                scheduling_service=self._scheduling_service
            )
        )
        self._validation_service = (
            validation_service
            if validation_service is not None
            else LLMAgentTaskRecoveryPreflightScheduleValidationService(scheduling_service=self._scheduling_service)
        )
        self._expiration_service = expiration_service
        self._blocking_service = blocking_service
        self._event_query_service = event_query_service
        self._store = store if store is not None else InMemoryAgentTaskRecoveryScheduleWakeStore()

    def wake(
        self, task_id: str, dependency_id: str = None, now: Optional[datetime] = None
    ) -> AgentTaskRecoveryScheduleWakeResult:
        """Consider every one of task_id's own currently-waiting
        schedules, waking each whose dependencies are now ready
        (optionally narrowed to schedules actually waiting on
        dependency_id) and preserving every other one unchanged.

        Raises:
            InvalidAgentTaskRecoveryScheduleDependencyWakeError: If
                task_id is not a non-empty string, dependency_id is
                given and is not a non-empty string, or now is given
                and is not a datetime
        """
        self._require_text(task_id, "task_id")
        if dependency_id is not None:
            self._require_text(dependency_id, "dependency_id")
        now = self._resolve_now(now)

        triggering_event_id = self._latest_dependency_event_id(task_id)

        outcomes = []
        for schedule in self._scheduling_service.list(task_id):
            if schedule.status != SCHEDULED:
                continue

            waiting, known_dependencies = self._waiting_state(task_id, schedule, now)
            if not waiting:
                continue
            if dependency_id is not None and known_dependencies and dependency_id not in known_dependencies:
                continue

            observation = self._reconciliation_service.reconcile(task_id, schedule.schedule_id).observations[0]
            outcomes.append(self._wake_one(task_id, schedule, observation, dependency_id, triggering_event_id, now))

        return AgentTaskRecoveryScheduleWakeResult(
            task_id=task_id, dependency_id=dependency_id, outcomes=tuple(outcomes),
            triggering_event_id=triggering_event_id, woken_at=now,
        )

    def wake_schedule(
        self, task_id: str, schedule_id: str, now: Optional[datetime] = None
    ) -> AgentTaskRecoveryScheduleWakeOutcome:
        """Consider task_id's exact schedule_id alone.

        Raises:
            InvalidAgentTaskRecoveryScheduleDependencyWakeError: If
                task_id/schedule_id is not a non-empty string, now is
                given and is not a datetime, or schedule_id names no
                recorded schedule for task_id
        """
        self._require_text(task_id, "task_id")
        self._require_text(schedule_id, "schedule_id")
        now = self._resolve_now(now)

        schedule = self._scheduling_service.get(task_id, schedule_id)
        if schedule is None:
            raise InvalidAgentTaskRecoveryScheduleDependencyWakeError(
                f"no schedule {schedule_id!r} is recorded for task_id {task_id!r}"
            )

        observation = self._reconciliation_service.reconcile(task_id, schedule_id).observations[0]
        triggering_event_id = self._latest_dependency_event_id(task_id)
        return self._wake_one(task_id, schedule, observation, None, triggering_event_id, now)

    def get_history(self, task_id: str) -> list:
        """Every wake ever recorded for task_id, oldest first."""
        self._require_text(task_id, "task_id")
        return self._store.list_for_task(task_id)

    def _wake_one(self, task_id, schedule, observation, dependency_id, triggering_event_id, now):
        if not observation.ready:
            return self._outcome(
                task_id, schedule, schedule.schedule_id, False, False,
                "dependencies are still not ready: " + ("; ".join(observation.blockers) or "blocked"),
                observation.blockers, now,
            )

        blockers = self._non_window_blockers(task_id, schedule.schedule_id, now)
        if blockers:
            return self._outcome(
                task_id, schedule, schedule.schedule_id, False, False,
                "cannot wake: " + "; ".join(blockers), observation.blockers, now,
            )

        if schedule.execute_at is None or schedule.execute_at <= now:
            return self._outcome(
                task_id, schedule, schedule.schedule_id, True, True,
                "already actionable", (), now,
            )

        # Deliberately never calls blocking_service.unblock() here: that
        # method's own precondition requires the schedule ALREADY be
        # within its execution window (Commit #3's own docstring/
        # "otherwise invalid" check), which is never true yet for a
        # schedule this class is about to bring back to actionable --
        # and there is nothing to clear anyway, since the NEW schedule_id
        # cancel()+schedule() below creates has never been blocked at
        # all. Commit #3's own block record stays exactly where it is,
        # against the now-cancelled original schedule_id, permanently
        # part of that history (Rule: "preserve wake history" /
        # Commit #3's own "Preserve transition history") -- inert, since
        # nothing ever dispatches against a cancelled schedule_id again.
        self._scheduling_service.cancel(task_id, schedule.schedule_id, reason="woken: dependencies are now ready")
        new_schedule = self._scheduling_service.schedule(task_id, schedule.preflight_id, execute_at=None)

        self._store.save(
            AgentTaskRecoveryScheduleWakeRecord(
                task_id=task_id, schedule_id=new_schedule.schedule_id, previous_schedule_id=schedule.schedule_id,
                preflight_id=schedule.preflight_id, dependency_id=dependency_id,
                reason="dependencies are now ready", triggering_event_id=triggering_event_id, woken_at=now,
            )
        )
        return self._outcome(
            task_id, new_schedule, schedule.schedule_id, True, False, "woken: dependencies are now ready", (), now,
        )

    def _non_window_blockers(self, task_id, schedule_id, now) -> list:
        validation = self._validation_service.validate(task_id, schedule_id)
        blockers = [
            reason for reason in validation.blocking_reasons if _WINDOW_NOT_REACHED_MARKER not in reason
        ]
        if self._expiration_service is not None:
            expiration = self._expiration_service.check(task_id, schedule_id, now=now)
            if expiration.expired:
                blockers.append(expiration.reason)
        return blockers

    def _waiting_state(self, task_id: str, schedule, now: datetime) -> tuple:
        """Whether schedule currently counts as "waiting" for wake()'s
        own purposes (Rule: "Find schedules currently waiting..."),
        plus the dependency_ids it is reliably known to be waiting on
        (empty when that attribution is not available).

        Commit #3's own durable blocking record, when one currently
        stands, is authoritative for BOTH questions at once -- its own
        `dependencies` is exactly the caller-supplied evidence recorded
        at block() time (Rule reused from that class's own docstring:
        "Preserve the dependency evidence... that caused the block").
        Without a current block record (no blocking_service configured,
        or this schedule was never explicitly blocked through it), a
        schedule deferred to a future execute_at by this package's own
        Commit #4 wait service still counts as "waiting" -- just with
        no reliable per-dependency attribution, so a dependency_id
        filter never excludes it (Rule: "Preserve schedules that remain
        blocked" implies never silently dropping a genuine candidate
        for lack of finer attribution).
        """
        if self._blocking_service is not None:
            record = self._blocking_service.get_latest(task_id, schedule.schedule_id)
            if record is not None and record.status == BLOCK_STATUS_BLOCKED:
                return True, record.dependencies
        if schedule.execute_at is not None and schedule.execute_at > now:
            return True, ()
        return False, ()

    def _latest_dependency_event_id(self, task_id: str) -> Optional[str]:
        if self._event_query_service is None:
            return None
        events = self._event_query_service.query(
            task_id=task_id, event_types=(DEPENDENCY_ADDED, DEPENDENCY_REMOVED)
        )
        return events[-1].event_id if events else None

    @staticmethod
    def _outcome(task_id, schedule, previous_schedule_id, woken, already_awake, reason, evidence, now):
        return AgentTaskRecoveryScheduleWakeOutcome(
            task_id=task_id, schedule_id=schedule.schedule_id, previous_schedule_id=previous_schedule_id,
            preflight_id=schedule.preflight_id, woken=woken, already_awake=already_awake, reason=reason,
            dependency_evidence=tuple(evidence), checked_at=now,
        )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryScheduleDependencyWakeError(
                f"{field_name} is required and must be a non-empty string"
            )

    @staticmethod
    def _resolve_now(now) -> datetime:
        if now is None:
            return datetime.now(timezone.utc)
        if not isinstance(now, datetime):
            raise InvalidAgentTaskRecoveryScheduleDependencyWakeError("now must be a datetime when given")
        return now
