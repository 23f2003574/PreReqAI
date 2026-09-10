from typing import Optional

from backend.agent_task_dependency_readiness_plan import AgentTaskDependencyReadinessPlan
from backend.agent_task_lifecycle import LLMAgentTaskLifecycleService, UnknownAgentTaskError

from .in_memory_store import InMemoryAgentTaskReadinessProjectionStore
from .models import AgentTaskReadinessProjection
from .store import AgentTaskReadinessProjectionStore


class InvalidReadinessProjectionError(ValueError):
    """Raised when project()/list_affected() is given invalid arguments."""


class LLMAgentTaskReadinessProjectionService:
    """Persists and serves the single latest, queryable readiness
    snapshot per task_id -- a derived read model, never a second source
    of truth (Rule: "task lifecycle/dependency state remains
    authoritative") and never a second cache, dependency graph, or
    readiness engine (Rule: "do not create another..."): project()
    never resolves anything itself, it only ever records the Commit #8
    AgentTaskDependencyReadinessPlan it is handed, and get() only ever
    reads what was already recorded.

    Persistence follows backend.agent_task_lifecycle.AgentTaskStore's
    own save/get shape exactly (an InMemoryAgentTaskReadinessProjectionStore
    by default, or a JSON-file-backed one built on the same backend.
    storage.AtomicJsonFile every other store in this project already
    uses) -- Rule: "reuse the repository's existing projection/state-
    storage patterns." save() always replaces whatever was stored for
    task_id before (Behavior 3), so this class only ever answers "what
    is the *latest* known readiness for task_id," never "show me its
    history" (Commit #2's own append-only TaskTransitionRecord already
    owns that shape, for a different question).

    get()/list_affected() never silently return a stale projection
    (Rule): both compare the stored source_version (task_id's own
    Commit #1 AgentTask.updated_at at projection time) against task_id's
    *current* updated_at, and return nothing for that task_id the
    moment they differ -- the same "evict/omit on any mismatch, no
    partial trust" discipline Commit #9's own cache.get() already
    established, deliberately scoped to task_id's own version only (see
    this module's own models.py for why a full-graph check, matching
    Commit #9's own fingerprint exactly, would make this a second cache
    rather than a queryable projection of one).
    """

    def __init__(
        self,
        lifecycle_service: LLMAgentTaskLifecycleService,
        store: AgentTaskReadinessProjectionStore = None,
    ):
        self._lifecycle_service = lifecycle_service
        self.store = store if store is not None else InMemoryAgentTaskReadinessProjectionStore()

    def project(
        self, task_id: str, readiness_result: AgentTaskDependencyReadinessPlan
    ) -> AgentTaskReadinessProjection:
        """Persist task_id's latest known readiness, derived from
        readiness_result (Behavior 1: "accept the output of the
        existing readiness/recalculation services" -- Commit #8's own
        AgentTaskDependencyReadinessPlan, exactly what Commit #12's own
        recalculate() produces per task too; see this module's own
        .recalculation for the bridge). Replaces whatever was
        previously projected for task_id (Behavior 3), deterministically
        and idempotently: projecting the same plan twice in a row always
        yields the same ready/blocking_reasons/pending_dependencies/
        failed_dependencies/source_version, differing only in
        projection_id/evaluated_at -- the same "identity/content is
        stable, only the store's own bookkeeping timestamp moves"
        convention every AgentTaskStore.save() in this series already
        keeps (Rule: "keep writes deterministic and idempotent").

        Raises:
            InvalidReadinessProjectionError: If task_id is missing or
                blank, readiness_result is not an
                AgentTaskDependencyReadinessPlan, or its own task_id
                does not match the task_id argument
        """
        if not task_id or not isinstance(task_id, str):
            raise InvalidReadinessProjectionError("task_id is required and must be a non-empty string")
        if not isinstance(readiness_result, AgentTaskDependencyReadinessPlan):
            raise InvalidReadinessProjectionError(
                f"readiness_result must be an AgentTaskDependencyReadinessPlan, got "
                f"{type(readiness_result).__name__}"
            )
        if readiness_result.task_id != task_id:
            raise InvalidReadinessProjectionError(
                f"readiness_result.task_id {readiness_result.task_id!r} does not match task_id {task_id!r}"
            )

        projection = AgentTaskReadinessProjection(
            task_id=task_id,
            ready=readiness_result.ready,
            blocking_reasons=self._blocking_reasons(readiness_result),
            pending_dependencies=list(readiness_result.pending_tasks),
            failed_dependencies=list(readiness_result.failed_tasks),
            source_version=self._current_version(task_id),
        )
        return self.store.save(projection)

    def get(self, task_id: str) -> Optional[AgentTaskReadinessProjection]:
        """task_id's latest projection, or None if nothing was ever
        projected for it, or the stored one is now stale (its own
        source_version no longer matches task_id's current
        AgentTask.updated_at)."""
        projection = self.store.get(task_id)
        if projection is None:
            return None
        if projection.source_version != self._current_version(task_id):
            return None
        return projection

    def list_affected(self, task_ids: list) -> list:
        """Every currently-valid (non-stale) projection among task_ids,
        in the given order -- a task_id with nothing projected, or a
        stale projection, is simply omitted (never raised for), the
        same per-item tolerance backend.agent_task_dependency_impact's
        own downstream traversal already keeps for a task_id that
        cannot be fully resolved.

        Raises:
            InvalidReadinessProjectionError: If task_ids is not a list
        """
        if not isinstance(task_ids, list):
            raise InvalidReadinessProjectionError("task_ids must be a list")
        return [projection for task_id in task_ids if (projection := self.get(task_id)) is not None]

    def _current_version(self, task_id: str):
        try:
            return self._lifecycle_service.get(task_id).updated_at
        except UnknownAgentTaskError:
            return None

    @staticmethod
    def _blocking_reasons(plan: AgentTaskDependencyReadinessPlan) -> list:
        return (
            [f"dependency {dep!r} has not completed yet" for dep in plan.pending_tasks]
            + [f"dependency {dep!r} failed or was cancelled" for dep in plan.failed_tasks]
            + [f"dependency {dep!r} is blocked by an upstream failure/cycle" for dep in plan.blocking_tasks]
            + [f"dependency {dep!r} could not be resolved (missing task or cycle)" for dep in plan.unresolved_tasks]
        )
