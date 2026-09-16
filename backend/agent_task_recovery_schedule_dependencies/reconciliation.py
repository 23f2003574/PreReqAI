from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

from backend.agent_task_dependency_resolution import LLMAgentTaskDependencyResolver
from backend.agent_task_recovery_scheduling import LLMAgentTaskRecoveryPreflightSchedulingService
from backend.storage import AtomicJsonFile

from .models import AgentTaskRecoveryScheduleDependencyResult
from .service import LLMAgentTaskRecoveryPreflightScheduleDependencyService

# The one state this module adds to Commit #1's own READY/BLOCKED/FAILED/
# UNKNOWN vocabulary -- reserved exclusively for "the dependency machinery
# itself raised while being asked" (Rule: "Fail closed when dependency
# state cannot be determined reliably"), never for an ordinary, cleanly-
# determined UNKNOWN (a missing dependency task, or no schedule at all --
# both already reliably reported as Commit #1's own UNKNOWN). Deliberately
# not added to Commit #1's own models.py DEPENDENCY_STATES: that
# frozenset describes states a live check() call can reliably reach;
# UNDETERMINED describes the one case where it could not.
UNDETERMINED = "undetermined"

# One dependency_task_id's own change, relative to its previous
# observation -- see LLMAgentTaskRecoveryPreflightScheduleDependencyReconciliationService's
# own docstring for the full classification rule.
CHANGE_NEWLY_BLOCKED = "newly_blocked"
CHANGE_RESOLVED = "resolved"
CHANGE_FAILED = "failed"
CHANGE_REMOVED = "removed"
CHANGE_CHANGED = "changed"
DEPENDENCY_CHANGE_KINDS = frozenset(
    {CHANGE_NEWLY_BLOCKED, CHANGE_RESOLVED, CHANGE_FAILED, CHANGE_REMOVED, CHANGE_CHANGED}
)

# The resolver's own six mutually-exclusive per-dependency buckets (see
# backend.agent_task_dependency_resolution.LLMAgentTaskDependencyResolver.
# resolve()'s own construction -- ready/pending/failed/blocked/unresolved/
# cyclic never overlap for the same dependency_task_id), named here so
# _bucket_map()/_classify() never hand-write these strings more than once.
_BUCKET_READY = "ready"
_BUCKET_PENDING = "pending"
_BUCKET_FAILED = "failed"
_BUCKET_BLOCKED = "blocked"
_BUCKET_UNRESOLVED = "unresolved"
_BUCKET_CYCLIC = "cyclic"


class InvalidAgentTaskRecoveryScheduleDependencyReconciliationError(ValueError):
    """Raised when reconcile()/reconcile_all()/get_history()/get_latest()
    is given invalid arguments."""


@dataclass(frozen=True)
class AgentTaskRecoveryScheduleDependencyObservation:
    """One immutable, append-only entry in one (task_id, schedule_id)'s
    own dependency reconciliation history (Rule: "Preserve prior
    observations/history") -- never updated or deleted once recorded,
    the same append-only discipline backend.agent_task_state_history.
    TaskTransitionRecord already establishes for a comparable case.

    Carries the exact same verdict shape Commit #1's own
    AgentTaskRecoveryScheduleDependencyResult already returns (ready/
    state/blockers/ready_dependencies/pending_dependencies/
    failed_dependencies/blocked_dependencies/unresolved_dependencies/
    cycles) -- never re-derived a second way, only ever recorded --
    plus two fields Commit #1's own result does not carry:

        reliable: False only when this exact pass could not actually
            determine dependency state at all (Rule: "Fail closed when
            dependency state cannot be determined reliably") -- every
            other field is then defensive/empty and state is
            UNDETERMINED. True for every ordinary outcome, including a
            reliably-determined Commit #1 UNKNOWN (a missing dependency
            task, or no schedule recorded at all).
        dependency_ids: every dependency_task_id actually reachable in
            task_id's own graph this pass, COMPLETED ones included --
            Commit #1's own six buckets alone can never tell a
            COMPLETED dependency (satisfied, no bucket at all) apart
            from one removed from the graph entirely (also no bucket);
            this is the one extra fact reconcile()'s own diff needs to
            tell "resolved" from "removed" (Rule: "Detect ... removed
            ... dependencies"). Empty when reliable is False.
    """

    task_id: str
    schedule_id: str
    preflight_id: Optional[str]
    ready: bool
    state: str
    reliable: bool
    blockers: tuple
    ready_dependencies: tuple
    pending_dependencies: tuple
    failed_dependencies: tuple
    blocked_dependencies: tuple
    unresolved_dependencies: tuple
    cycles: tuple
    dependency_ids: tuple
    observed_at: datetime
    observation_id: str = field(default_factory=lambda: str(uuid4()))

    @classmethod
    def from_check(
        cls, result: AgentTaskRecoveryScheduleDependencyResult, dependency_ids: tuple
    ) -> "AgentTaskRecoveryScheduleDependencyObservation":
        return cls(
            task_id=result.task_id, schedule_id=result.schedule_id, preflight_id=result.preflight_id,
            ready=result.ready, state=result.state, reliable=True, blockers=result.blockers,
            ready_dependencies=result.ready_dependencies, pending_dependencies=result.pending_dependencies,
            failed_dependencies=result.failed_dependencies, blocked_dependencies=result.blocked_dependencies,
            unresolved_dependencies=result.unresolved_dependencies, cycles=result.cycles,
            dependency_ids=dependency_ids, observed_at=result.checked_at,
        )

    @classmethod
    def undetermined(
        cls, task_id: str, schedule_id: str, preflight_id: Optional[str], reason: str
    ) -> "AgentTaskRecoveryScheduleDependencyObservation":
        return cls(
            task_id=task_id, schedule_id=schedule_id, preflight_id=preflight_id,
            ready=False, state=UNDETERMINED, reliable=False, blockers=(reason,),
            ready_dependencies=(), pending_dependencies=(), failed_dependencies=(),
            blocked_dependencies=(), unresolved_dependencies=(), cycles=(), dependency_ids=(),
            observed_at=datetime.now(timezone.utc),
        )

    def to_dict(self) -> dict:
        data = asdict(self)
        data["observed_at"] = self.observed_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "AgentTaskRecoveryScheduleDependencyObservation":
        payload = dict(data)
        value = payload.get("observed_at")
        if isinstance(value, str):
            payload["observed_at"] = datetime.fromisoformat(value)
        for key in (
            "blockers", "ready_dependencies", "pending_dependencies", "failed_dependencies",
            "blocked_dependencies", "unresolved_dependencies", "cycles", "dependency_ids",
        ):
            if key in payload and payload[key] is not None:
                payload[key] = tuple(payload[key])
        return cls(**payload)


@dataclass(frozen=True)
class AgentTaskRecoveryScheduleDependencyChange:
    """One dependency_task_id whose own standing changed for one
    schedule, relative to its immediately preceding observation.

    kind is exactly one of DEPENDENCY_CHANGE_KINDS:
        newly_blocked: now in the "blocked" bucket (transitively
            tainted), and was not before.
        resolved: was in an outstanding bucket before (pending/ready/
            failed/blocked/unresolved/cyclic) and is now COMPLETED --
            still present in the graph (dependency_ids), simply no
            longer outstanding.
        failed: now failed or part of a cycle, and was not before.
        removed: was present in the graph before and is no longer
            reachable in it at all (the edge itself, or an intermediate
            node, was removed) -- distinct from "resolved": the
            dependency did not finish, it disappeared.
        changed: any other bucket transition (including a brand-new
            dependency edge that is not itself newly_blocked/failed).

    Never produced by comparing against an unreliable (Commit #1
    UNDETERMINED) observation on either side (Rule: "Fail closed" --
    an undetermined pass can never itself stand for a real transition).
    """

    schedule_id: str
    preflight_id: Optional[str]
    dependency_task_id: str
    kind: str
    previous_bucket: Optional[str]
    current_bucket: Optional[str]


@dataclass(frozen=True)
class AgentTaskRecoveryScheduleDependencyReconciliationResult:
    """LLMAgentTaskRecoveryPreflightScheduleDependencyReconciliationService.
    reconcile()/reconcile_all()'s own complete report of one reconciliation
    pass -- covering every schedule that call actually looked at (exactly
    one for reconcile(task_id, schedule_id), every one of task_id's own
    schedules for reconcile_all()/reconcile(task_id)).

    changes carries every AgentTaskRecoveryScheduleDependencyChange
    detected across every reconciled schedule this pass -- unaffected
    dependencies never produce an entry at all (the same "only actually-
    affected items are reported" convention backend.
    agent_task_recovery_scheduling.AgentTaskRecoveryScheduleReconciliationResult
    already establishes for a comparable case), so an empty tuple here
    means every reconciled schedule's dependency state is unchanged
    since its own previous observation.

    reliable is exactly `not unreliable_schedule_ids`: False the moment
    even one reconciled schedule's dependency state could not be
    determined this pass (Rule: "Fail closed").
    """

    task_id: str
    observations: tuple
    changes: tuple
    reliable: bool
    unreliable_schedule_ids: tuple
    reconciled_at: datetime


class AgentTaskRecoveryScheduleDependencyObservationStore(ABC):
    """Append-only persistence for AgentTaskRecoveryScheduleDependencyObservation
    records -- the same save()/list_for_-- split backend.
    agent_task_state_history.AgentTaskTransitionStore already establishes
    for its own, unrelated append-only trail. There is no update() or
    delete(): an observation is never overwritten or removed once
    recorded (Rule: "Preserve prior observations/history")."""

    @abstractmethod
    def save(self, observation: AgentTaskRecoveryScheduleDependencyObservation) -> AgentTaskRecoveryScheduleDependencyObservation:
        ...

    @abstractmethod
    def list_for_schedule(self, task_id: str, schedule_id: str) -> list:
        ...

    @abstractmethod
    def list_for_task(self, task_id: str) -> list:
        ...


class InMemoryAgentTaskRecoveryScheduleDependencyObservationStore(AgentTaskRecoveryScheduleDependencyObservationStore):
    """Stores dependency reconciliation observations in memory, for
    development and testing."""

    def __init__(self):
        self._by_schedule: dict = {}

    def save(self, observation: AgentTaskRecoveryScheduleDependencyObservation) -> AgentTaskRecoveryScheduleDependencyObservation:
        stored = deepcopy(observation)
        self._by_schedule.setdefault((observation.task_id, observation.schedule_id), []).append(stored)
        return deepcopy(stored)

    def list_for_schedule(self, task_id: str, schedule_id: str) -> list:
        entries = self._by_schedule.get((task_id, schedule_id), [])
        return [deepcopy(entry) for entry in sorted(entries, key=lambda item: item.observed_at)]

    def list_for_task(self, task_id: str) -> list:
        entries = [entry for (t, _), entries in self._by_schedule.items() if t == task_id for entry in entries]
        return [deepcopy(entry) for entry in sorted(entries, key=lambda item: item.observed_at)]


class JsonAgentTaskRecoveryScheduleDependencyObservationStore(AgentTaskRecoveryScheduleDependencyObservationStore):
    """Persists dependency reconciliation observations to a JSON file,
    keyed by f"{task_id}::{schedule_id}"."""

    def __init__(self, path: str | Path):
        self.file = AtomicJsonFile(path, default_factory=dict)

    @staticmethod
    def _key(task_id: str, schedule_id: str) -> str:
        return f"{task_id}::{schedule_id}"

    def save(self, observation: AgentTaskRecoveryScheduleDependencyObservation) -> AgentTaskRecoveryScheduleDependencyObservation:
        records = self.file.read()
        key = self._key(observation.task_id, observation.schedule_id)
        records.setdefault(key, []).append(observation.to_dict())
        self.file.write(records)
        return deepcopy(observation)

    def list_for_schedule(self, task_id: str, schedule_id: str) -> list:
        records = self.file.read()
        matching = [
            AgentTaskRecoveryScheduleDependencyObservation.from_dict(data)
            for data in records.get(self._key(task_id, schedule_id), [])
        ]
        return sorted(matching, key=lambda item: item.observed_at)

    def list_for_task(self, task_id: str) -> list:
        records = self.file.read()
        prefix = f"{task_id}::"
        matching = [
            AgentTaskRecoveryScheduleDependencyObservation.from_dict(data)
            for key, entries in records.items() if key.startswith(prefix)
            for data in entries
        ]
        return sorted(matching, key=lambda item: item.observed_at)


class LLMAgentTaskRecoveryPreflightScheduleDependencyReconciliationService:
    """Keeps a Commit #1 schedule's own recorded dependency standing
    synchronized with task_id's CURRENT dependency graph -- never a
    second dependency resolver or scheduling/state-management system
    (Rule: "Do not create another dependency resolver" / "Update only
    scheduling/dependency reconciliation state"): every dependency fact
    here comes from Commit #1's own dependency_service.check() (the
    ready/state/blockers verdict, re-checked live, never cached) plus a
    direct call to that SAME Commit #6-of-agent_task_dependency_resolution
    LLMAgentTaskDependencyResolver.resolve() already wired into it (for
    ordered_dependencies -- see AgentTaskRecoveryScheduleDependencyObservation's
    own docstring for why that extra read is needed); nothing here
    re-derives dependency traversal, cycle detection, or task-lifecycle
    state a second way.

    reconcile(task_id, schedule_id)/reconcile_all(task_id) both ALWAYS
    record one new AgentTaskRecoveryScheduleDependencyObservation per
    schedule looked at (Rule: "Preserve prior observations/history" --
    an append-only log by construction, nothing here ever overwrites or
    deletes a prior entry) and compare it against that exact schedule's
    own immediately preceding observation (if any) to produce this
    pass's own AgentTaskRecoveryScheduleDependencyChange entries (Rule:
    "Detect newly blocked, resolved, failed, removed, or changed
    dependencies" -- see that dataclass's own docstring for the full
    classification). A schedule reconciled for the very first time has
    nothing to compare against yet: its own observation is recorded as
    this series' own baseline, with zero changes reported (nothing else
    to report yet).

    Idempotent (Rule): reconciling an unchanged dependency graph twice
    always yields the exact same ready/state/blockers verdict and an
    empty `changes` tuple on the second call (a new observation row is
    still appended each time -- by design, it IS the history -- but the
    DECISION it carries never drifts for identical underlying state).

    Fails closed (Rule: "Fail closed when dependency state cannot be
    determined reliably"): dependency_service.check()/dependency_resolver.
    resolve() can each raise (most commonly Commit #1-of-agent_task_lifecycle's
    own UnknownAgentTaskError, when task_id itself is not known to the
    exact lifecycle_service this reconciliation service's own resolver
    was built over) -- any such exception is caught, never propagated,
    and recorded as this pass's own UNDETERMINED, reliable=False
    observation (ready=False, a diagnostic blocker naming the error)
    rather than either crashing or silently defaulting to ready=True.
    An UNDETERMINED pass is also never diffed against (see
    AgentTaskRecoveryScheduleDependencyChange's own docstring): it can
    never itself stand for a real dependency transition either way.

    Never executes recovery, and never touches schedule status itself
    (Rule): nothing here ever calls Commit #1-of-agent_task_recovery_scheduling's
    own schedule()/cancel(), or anything from
    backend.agent_task_recovery_guardrails' own write paths -- the only
    write anywhere in this class is this module's own observation store.

    Feeds dispatch eligibility (Rule: "Feed the reconciled state back
    into the existing schedule validation/dispatch path"): check(),
    below, is the bridge -- it performs one real reconcile() (recording
    history exactly as any other call does) and hands back that exact
    schedule's own freshly-recorded observation, which already carries
    .ready/.blockers in the same shape Commit #1's own
    LLMAgentTaskRecoveryPreflightScheduleDependencyService.check() does.
    A caller wires THIS service (rather than Commit #1's bare gate)
    into backend.agent_task_recovery_scheduling.
    LLMAgentTaskRecoveryPreflightScheduleValidationService's own
    optional, duck-typed dependency_service parameter to make every
    validate()/dispatch() call reconcile fresh, so a stale dependency
    decision can never block or permit dispatch incorrectly.
    """

    def __init__(
        self,
        scheduling_service: LLMAgentTaskRecoveryPreflightSchedulingService = None,
        dependency_service: LLMAgentTaskRecoveryPreflightScheduleDependencyService = None,
        dependency_resolver: LLMAgentTaskDependencyResolver = None,
        store: AgentTaskRecoveryScheduleDependencyObservationStore = None,
    ):
        """
        Args:
            scheduling_service: The exact
                backend.agent_task_recovery_scheduling.
                LLMAgentTaskRecoveryPreflightSchedulingService instance
                holding task_id's real schedules. Defaults to a fresh
                instance (used by reconcile_all()'s own list() call, and
                to build a default dependency_service when none is
                given) -- pass the real instance holding a task's actual
                schedules for reconcile_all() to ever find anything.
            dependency_service: Commit #1's own gate. Defaults to a
                fresh LLMAgentTaskRecoveryPreflightScheduleDependencyService
                built over this exact scheduling_service/dependency_resolver,
                so the gate's own verdict and this service's own
                dependency_ids read are never answering from two
                divergently-configured collaborators.
            dependency_resolver: No default (mirrors Commit #1's own
                dependency_resolver -- it must be the exact instance
                built over task_id's real dependency graph). Enables
                dependency_ids (ordered_dependencies, for resolved-vs-
                removed detection); without one, dependency_ids is
                always empty and every removed/resolved distinction
                degrades to "removed" (the safer, more conservative
                fail-closed-adjacent reading when the graph's own full
                reachable set cannot be inspected at all).
            store: Defaults to a fresh
                InMemoryAgentTaskRecoveryScheduleDependencyObservationStore.
        """
        self._scheduling_service = (
            scheduling_service if scheduling_service is not None else LLMAgentTaskRecoveryPreflightSchedulingService()
        )
        self._dependency_resolver = dependency_resolver
        self._dependency_service = (
            dependency_service
            if dependency_service is not None
            else LLMAgentTaskRecoveryPreflightScheduleDependencyService(
                scheduling_service=self._scheduling_service, dependency_resolver=dependency_resolver
            )
        )
        self._store = store if store is not None else InMemoryAgentTaskRecoveryScheduleDependencyObservationStore()

    def check(self, task_id: str, schedule_id: str) -> AgentTaskRecoveryScheduleDependencyObservation:
        """Reconcile task_id's exact schedule_id and hand back its own
        freshly-recorded observation -- the bridge this service exposes
        for backend.agent_task_recovery_scheduling.
        LLMAgentTaskRecoveryPreflightScheduleValidationService's own
        optional dependency_service hook (see this class's own
        docstring)."""
        return self.reconcile(task_id, schedule_id).observations[0]

    def reconcile(
        self, task_id: str, schedule_id: str = None
    ) -> AgentTaskRecoveryScheduleDependencyReconciliationResult:
        """Reconcile task_id's exact schedule_id, or every one of
        task_id's own schedules when schedule_id is omitted (delegates
        directly to reconcile_all()).

        Raises:
            InvalidAgentTaskRecoveryScheduleDependencyReconciliationError:
                If task_id is not a non-empty string, or schedule_id is
                given and is not a non-empty string
        """
        self._require_text(task_id, "task_id")
        if schedule_id is None:
            return self.reconcile_all(task_id)
        self._require_text(schedule_id, "schedule_id")
        return self._run(task_id, [schedule_id])

    def reconcile_all(self, task_id: str) -> AgentTaskRecoveryScheduleDependencyReconciliationResult:
        """Reconcile every schedule ever recorded for task_id.

        Raises:
            InvalidAgentTaskRecoveryScheduleDependencyReconciliationError:
                If task_id is not a non-empty string
        """
        self._require_text(task_id, "task_id")
        schedule_ids = [schedule.schedule_id for schedule in self._scheduling_service.list(task_id)]
        return self._run(task_id, schedule_ids)

    def get_history(self, task_id: str, schedule_id: str) -> list:
        """Every observation ever recorded for task_id's exact
        schedule_id, oldest first -- never mutated or trimmed (Rule:
        "Preserve prior observations/history")."""
        self._require_text(task_id, "task_id")
        self._require_text(schedule_id, "schedule_id")
        return self._store.list_for_schedule(task_id, schedule_id)

    def get_latest(self, task_id: str, schedule_id: str):
        """The most recent observation for task_id's exact schedule_id,
        or None if it has never been reconciled."""
        history = self.get_history(task_id, schedule_id)
        return history[-1] if history else None

    def _run(self, task_id: str, schedule_ids: list) -> AgentTaskRecoveryScheduleDependencyReconciliationResult:
        observations: list = []
        changes: list = []
        unreliable: list = []

        for schedule_id in schedule_ids:
            previous = self.get_latest(task_id, schedule_id)
            observation = self._observe(task_id, schedule_id, previous)
            stored = self._store.save(observation)
            observations.append(stored)
            if not stored.reliable:
                unreliable.append(schedule_id)
            changes.extend(self._diff(previous, stored))

        return AgentTaskRecoveryScheduleDependencyReconciliationResult(
            task_id=task_id, observations=tuple(observations), changes=tuple(changes),
            reliable=not unreliable, unreliable_schedule_ids=tuple(unreliable),
            reconciled_at=datetime.now(timezone.utc),
        )

    def _observe(
        self, task_id: str, schedule_id: str, previous: Optional[AgentTaskRecoveryScheduleDependencyObservation]
    ) -> AgentTaskRecoveryScheduleDependencyObservation:
        try:
            result = self._dependency_service.check(task_id, schedule_id)
            dependency_ids = self._reachable_ids(task_id)
        except Exception as error:
            preflight_id = previous.preflight_id if previous is not None else None
            return AgentTaskRecoveryScheduleDependencyObservation.undetermined(
                task_id, schedule_id, preflight_id, f"dependency state could not be determined reliably: {error}"
            )
        return AgentTaskRecoveryScheduleDependencyObservation.from_check(result, dependency_ids)

    def _reachable_ids(self, task_id: str) -> tuple:
        if self._dependency_resolver is None:
            return ()
        resolution = self._dependency_resolver.resolve(task_id)
        return tuple(
            sorted(set(resolution.ordered_dependencies) | set(resolution.unresolved_dependencies) | set(resolution.cycles))
        )

    def _diff(
        self,
        previous: Optional[AgentTaskRecoveryScheduleDependencyObservation],
        current: AgentTaskRecoveryScheduleDependencyObservation,
    ) -> list:
        if previous is None or not previous.reliable or not current.reliable:
            return []

        previous_buckets = self._bucket_map(previous)
        current_buckets = self._bucket_map(current)
        all_ids = set(previous.dependency_ids) | set(current.dependency_ids) | set(previous_buckets) | set(current_buckets)

        changes = []
        for dependency_task_id in sorted(all_ids):
            previous_bucket = previous_buckets.get(dependency_task_id)
            current_bucket = current_buckets.get(dependency_task_id)
            previous_present = dependency_task_id in previous.dependency_ids or previous_bucket is not None
            current_present = dependency_task_id in current.dependency_ids or current_bucket is not None
            if previous_bucket == current_bucket and previous_present == current_present:
                continue
            kind = self._classify(previous_bucket, current_bucket, previous_present, current_present)
            changes.append(
                AgentTaskRecoveryScheduleDependencyChange(
                    schedule_id=current.schedule_id, preflight_id=current.preflight_id,
                    dependency_task_id=dependency_task_id, kind=kind,
                    previous_bucket=previous_bucket, current_bucket=current_bucket,
                )
            )
        return changes

    @staticmethod
    def _bucket_map(observation: AgentTaskRecoveryScheduleDependencyObservation) -> dict:
        buckets: dict = {}
        for dependency_task_id in observation.ready_dependencies:
            buckets[dependency_task_id] = _BUCKET_READY
        for dependency_task_id in observation.pending_dependencies:
            buckets[dependency_task_id] = _BUCKET_PENDING
        for dependency_task_id in observation.failed_dependencies:
            buckets[dependency_task_id] = _BUCKET_FAILED
        for dependency_task_id in observation.blocked_dependencies:
            buckets[dependency_task_id] = _BUCKET_BLOCKED
        for dependency_task_id in observation.unresolved_dependencies:
            buckets[dependency_task_id] = _BUCKET_UNRESOLVED
        for dependency_task_id in observation.cycles:
            buckets[dependency_task_id] = _BUCKET_CYCLIC
        return buckets

    @staticmethod
    def _classify(previous_bucket, current_bucket, previous_present: bool, current_present: bool) -> str:
        if previous_present and not current_present:
            return CHANGE_REMOVED
        if not previous_present and current_present:
            if current_bucket in (_BUCKET_FAILED, _BUCKET_CYCLIC):
                return CHANGE_FAILED
            if current_bucket == _BUCKET_BLOCKED:
                return CHANGE_NEWLY_BLOCKED
            return CHANGE_CHANGED
        if current_bucket in (_BUCKET_FAILED, _BUCKET_CYCLIC) and previous_bucket not in (_BUCKET_FAILED, _BUCKET_CYCLIC):
            return CHANGE_FAILED
        if current_bucket == _BUCKET_BLOCKED and previous_bucket != _BUCKET_BLOCKED:
            return CHANGE_NEWLY_BLOCKED
        if current_bucket is None:
            return CHANGE_RESOLVED
        return CHANGE_CHANGED

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryScheduleDependencyReconciliationError(
                f"{field_name} is required and must be a non-empty string"
            )
