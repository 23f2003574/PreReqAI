from datetime import datetime, timezone
from typing import Optional

from backend.agent_task_dependencies import LLMAgentTaskDependencyService
from backend.agent_task_dependency_resolution import LLMAgentTaskDependencyResolver
from backend.agent_task_recovery_guardrails import LLMAgentTaskRecoveryPreflightStore

from .models import (
    BLOCKED,
    COMPLETED,
    CYCLIC,
    FAILED,
    PENDING,
    READY,
    UNRESOLVED,
    AgentTaskDependencySnapshotEntry,
    AgentTaskDependencySnapshotStateChange,
    AgentTaskRecoveryPreflightDependencySnapshot,
    AgentTaskRecoveryPreflightDependencySnapshotDiff,
)
from .store import AgentTaskRecoveryPreflightDependencySnapshotStore, InMemoryAgentTaskRecoveryPreflightDependencySnapshotStore


class InvalidAgentTaskRecoveryPreflightDependencySnapshotError(ValueError):
    """Raised when create()/get()/diff() is given invalid arguments, when
    create() names a preflight_id that is not actually recorded for
    task_id, or when diff() names a snapshot_id that does not exist for
    task_id."""


class LLMAgentTaskRecoveryPreflightDependencySnapshotService:
    """Persists a point-in-time capture of task_id's dependency graph,
    bound to one exact preflight, so a later reconciliation can compare
    against the EXACT graph that existed when a recovery schedule was
    prepared -- never a second dependency graph engine (Rule: "Reuse
    existing dependency resolver; don't duplicate dependency semantics"):
    every dependency this class ever looks at comes from backend.
    agent_task_dependency_resolution.LLMAgentTaskDependencyResolver.
    resolve() (transitive, preferred, when a dependency_resolver is
    supplied) or, as a fallback, backend.agent_task_dependencies.
    LLMAgentTaskDependencyService.check_dependencies() (direct only, when
    only a dependency_service is given) -- the exact same dual-
    collaborator, resolver-takes-priority shape backend.
    agent_task_recovery_schedule_dependencies.
    LLMAgentTaskRecoveryPreflightScheduleDependencyService and backend.
    agent_task_readiness.LLMAgentTaskReadinessService already establish
    for a comparable case. With neither collaborator supplied, a snapshot
    simply has no dependencies to capture -- there is no dependency
    infrastructure configured to consult.

    Bound to the exact (task_id, preflight_id) (Rule: "Capture ... for
    the exact task/preflight"; "exact task/preflight binding"): create()
    verifies preflight_id is actually recorded for task_id via backend.
    agent_task_recovery_guardrails' own LLMAgentTaskRecoveryPreflightStore
    before ever building a snapshot -- a preflight_id that belongs to a
    different task_id, or does not exist at all, is refused outright,
    never silently accepted. A fresh, empty default preflight_store (like
    every other optional collaborator default in this project) means
    create() will refuse every call until the caller wires the SAME
    preflight_store instance that actually recorded the preflight --
    the same "always wire the real one from the stack" sharp edge this
    project's own comparable services already document.

    Preserves immutable snapshots (Rule): AgentTaskRecoveryPreflight
    DependencySnapshot is a frozen dataclass, and the underlying store
    this class writes through has no update()/delete() at all -- once
    created, a snapshot is never rewritten, only ever read back by get()
    or compared against by diff().

    diff() is read-only, with no scheduling/recovery side effects (Rule):
    it only ever calls get() (a pure read) and re-runs the same resolver/
    dependency-service read create() itself already uses -- nothing here
    ever calls transition(), schedule(), authorize(), or any other write
    path anywhere else in this repository.

    Every real (non-cyclic, non-unresolved) dependency reachable from
    task_id is captured, whether or not it is already COMPLETED (Rule:
    "capture the resolved dependency IDs and relevant states") -- unlike
    backend.agent_task_dependency_resolution.AgentTaskDependencyResolution's
    own six buckets (which, by design, say nothing at all about an
    already-COMPLETED dependency), a snapshot entry exists for EVERY
    reachable dependency, with COMPLETED made an explicit state value
    rather than an absence. This is what lets diff() tell "the dependency
    completed" (still present, now COMPLETED) apart from "the dependency
    edge was removed from the graph" (no longer present at all) without
    needing the second, ordered_dependencies-based re-read backend.
    agent_task_recovery_schedule_dependencies' own reconciliation.py
    needed to solve the identical ambiguity for its own, narrower six-
    bucket result.
    """

    def __init__(
        self,
        dependency_resolver: LLMAgentTaskDependencyResolver = None,
        dependency_service: LLMAgentTaskDependencyService = None,
        preflight_store: LLMAgentTaskRecoveryPreflightStore = None,
        store: AgentTaskRecoveryPreflightDependencySnapshotStore = None,
    ):
        """
        Args:
            dependency_resolver: No default (mirrors
                LLMAgentTaskReadinessService's own dependency_resolver --
                it must be the exact instance built over a task's real
                dependency graph). Enables the *transitive*
                ready/pending/failed/blocked/unresolved/cyclic capture,
                and takes priority over dependency_service when both are
                given.
            dependency_service: No default; enables only a *direct*-
                dependencies capture (via check_dependencies()), and only
                when dependency_resolver is not also given.
            preflight_store: Defaults to a fresh, empty
                LLMAgentTaskRecoveryPreflightStore; pass the real
                instance holding a task's actual preflights for create()
                to ever find one to bind against.
            store: Defaults to a fresh
                InMemoryAgentTaskRecoveryPreflightDependencySnapshotStore.
        """
        self._dependency_resolver = dependency_resolver
        self._dependency_service = dependency_service
        self._preflight_store = preflight_store if preflight_store is not None else LLMAgentTaskRecoveryPreflightStore()
        self._store = store if store is not None else InMemoryAgentTaskRecoveryPreflightDependencySnapshotStore()

    def create(self, task_id: str, preflight_id: str) -> AgentTaskRecoveryPreflightDependencySnapshot:
        """Capture task_id's current dependency graph, bound to
        preflight_id.

        Raises:
            InvalidAgentTaskRecoveryPreflightDependencySnapshotError: If
                task_id/preflight_id is not a non-empty string, or
                preflight_id is not a preflight actually recorded for
                task_id
        """
        self._require_text(task_id, "task_id")
        self._require_text(preflight_id, "preflight_id")

        if not any(record.preflight_id == preflight_id for record in self._preflight_store.history(task_id)):
            raise InvalidAgentTaskRecoveryPreflightDependencySnapshotError(
                f"no preflight {preflight_id!r} is recorded for task_id {task_id!r}"
            )

        entries = self._entries(task_id)
        snapshot = AgentTaskRecoveryPreflightDependencySnapshot(
            task_id=task_id,
            preflight_id=preflight_id,
            dependencies=entries,
            captured_at=self._now(),
        )
        return self._store.save(snapshot)

    def get(self, task_id: str, snapshot_id: str) -> Optional[AgentTaskRecoveryPreflightDependencySnapshot]:
        """task_id's exact snapshot_id -- None if it does not exist or
        belongs to a different task_id.

        Raises:
            InvalidAgentTaskRecoveryPreflightDependencySnapshotError: If
                task_id or snapshot_id is not a non-empty string
        """
        self._require_text(task_id, "task_id")
        self._require_text(snapshot_id, "snapshot_id")

        record = self._store.get(snapshot_id)
        if record is None or record.task_id != task_id:
            return None
        return record

    def diff(self, task_id: str, snapshot_id: str) -> AgentTaskRecoveryPreflightDependencySnapshotDiff:
        """Compare task_id's exact, already-persisted snapshot_id against
        task_id's CURRENT dependency graph, right now. Read-only: never
        mutates the snapshot, the dependency graph, or any
        scheduling/recovery state.

        Raises:
            InvalidAgentTaskRecoveryPreflightDependencySnapshotError: If
                task_id/snapshot_id is not a non-empty string, or names
                no recorded snapshot for task_id
        """
        snapshot = self.get(task_id, snapshot_id)
        if snapshot is None:
            raise InvalidAgentTaskRecoveryPreflightDependencySnapshotError(
                f"no snapshot {snapshot_id!r} is recorded for task_id {task_id!r}"
            )

        previous = {entry.dependency_task_id: entry.state for entry in snapshot.dependencies}
        current = {entry.dependency_task_id: entry.state for entry in self._entries(task_id)}

        added = tuple(sorted(set(current) - set(previous)))
        removed = tuple(sorted(set(previous) - set(current)))

        resolved, newly_blocked, state_changed = [], [], []
        for dependency_task_id in sorted(set(previous) & set(current)):
            previous_state = previous[dependency_task_id]
            current_state = current[dependency_task_id]
            if previous_state == current_state:
                continue
            if current_state == COMPLETED:
                resolved.append(dependency_task_id)
            elif current_state == BLOCKED and previous_state != BLOCKED:
                newly_blocked.append(dependency_task_id)
            else:
                state_changed.append(
                    AgentTaskDependencySnapshotStateChange(
                        dependency_task_id=dependency_task_id,
                        previous_state=previous_state,
                        current_state=current_state,
                    )
                )

        return AgentTaskRecoveryPreflightDependencySnapshotDiff(
            task_id=task_id,
            snapshot_id=snapshot_id,
            preflight_id=snapshot.preflight_id,
            added=added,
            removed=removed,
            resolved=tuple(resolved),
            newly_blocked=tuple(newly_blocked),
            state_changed=tuple(state_changed),
            changed=bool(added or removed or resolved or newly_blocked or state_changed),
            diffed_at=self._now(),
        )

    def _entries(self, task_id: str) -> tuple:
        states = self._current_states(task_id)
        return tuple(
            AgentTaskDependencySnapshotEntry(dependency_task_id=dependency_task_id, state=state)
            for dependency_task_id, state in sorted(states.items())
        )

    def _current_states(self, task_id: str) -> dict:
        """dependency_task_id -> effective state, for every dependency
        currently reachable from task_id -- the exact same computation
        create() and diff() both build their comparison from."""
        if self._dependency_resolver is not None:
            resolution = self._dependency_resolver.resolve(task_id)
            cyclic = set(resolution.cycles) - {task_id}
            universe = set(resolution.ordered_dependencies) | set(resolution.unresolved_dependencies) | cyclic

            states = {}
            for dependency_task_id in resolution.failed_dependencies:
                states[dependency_task_id] = FAILED
            for dependency_task_id in cyclic:
                states[dependency_task_id] = CYCLIC
            for dependency_task_id in resolution.unresolved_dependencies:
                states[dependency_task_id] = UNRESOLVED
            for dependency_task_id in resolution.blocked_dependencies:
                states[dependency_task_id] = BLOCKED
            for dependency_task_id in resolution.pending_dependencies:
                states[dependency_task_id] = PENDING
            for dependency_task_id in resolution.ready_dependencies:
                states[dependency_task_id] = READY
            for dependency_task_id in universe - set(states):
                states[dependency_task_id] = COMPLETED
            return states

        if self._dependency_service is not None:
            result = self._dependency_service.check_dependencies(task_id)
            universe = set(result.dependencies)

            states = {}
            for dependency_task_id in result.failed:
                states[dependency_task_id] = FAILED
            for dependency_task_id in result.blocked:
                states[dependency_task_id] = BLOCKED
            for dependency_task_id in result.pending:
                states[dependency_task_id] = PENDING
            for dependency_task_id in universe - set(states):
                states[dependency_task_id] = COMPLETED
            return states

        return {}

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not value or not isinstance(value, str):
            raise InvalidAgentTaskRecoveryPreflightDependencySnapshotError(
                f"{field_name} is required and must be a non-empty string"
            )
