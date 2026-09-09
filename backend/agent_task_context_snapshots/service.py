from backend.agent_task_context import LLMAgentTaskContext, LLMAgentTaskContextService
from backend.agent_task_context_resolution import LLMAgentTaskContextResolver

from .in_memory_store import InMemoryTaskContextSnapshotStore
from .models import TaskContextSnapshot
from .store import TaskContextSnapshotStore


class UnknownTaskContextSnapshotError(KeyError):
    """Raised when get()/restore() names a snapshot_id that was never created."""


class CrossTaskSnapshotError(ValueError):
    """Raised when restore() is given a snapshot_id that belongs to a
    different task (and therefore a different scope) than task_id."""


class LLMAgentTaskContextSnapshotService:
    """Creates, reads, and restores immutable snapshots of a task's
    *resolved* context -- what an agent execution actually saw, not just
    the task's own stored relevant_context.

    Not a second snapshot/versioning system: create() calls Commit #2's
    own backend.agent_task_context_resolution.LLMAgentTaskContextResolver.
    resolve() to capture the exact resolved_context/provenance at this
    moment (a read-only call -- nothing in the project context or memory
    stores is ever touched), and restore() writes the snapshot's own
    relevant_context/provenance back through Commit #1's own
    LLMAgentTaskContextService.update() -- the same append-only,
    never-erasing persistence this whole series already relies on --
    rather than a second write path. Persistence for the snapshots
    themselves follows the exact save/get/list_for_task/latest_for_task
    shape backend.llm.context_version.LLMContextVersionStore already
    establishes for an immutable, monotonically-versioned record (an
    InMemoryTaskContextSnapshotStore by default, or a JSON-file-backed
    store built on the same backend.storage.AtomicJsonFile).

    context_version is computed the same way LLMContextVersionService.
    snapshot() computes its own (next = previous + 1, 1 if none) --
    that service itself isn't reused directly because it snapshots a
    single backend.llm.project_context.LLMProjectContext's own content,
    a mismatched domain for a task's composite resolved context (the
    same reasoning Commit #7 already used to prefer Commit #1's own
    snapshot() over LLMContextVersionService for a materially identical
    task-context-versioning need).
    """

    def __init__(
        self,
        task_context_service: LLMAgentTaskContextService,
        resolver: LLMAgentTaskContextResolver,
        store: TaskContextSnapshotStore = None,
    ):
        self._task_context_service = task_context_service
        self._resolver = resolver
        self.store = store if store is not None else InMemoryTaskContextSnapshotStore()

    def create(self, task_id: str) -> TaskContextSnapshot:
        """Snapshot task_id's resolved context right now.

        Raises:
            UnknownTaskContextError: If task_id was never created
                (propagated from Commit #1's own get(), unwrapped)
        """
        task_context = self._task_context_service.get(task_id)
        resolved = self._resolver.resolve(task_id, task_context.agent_id, task_context.scope_id)

        previous = self.store.latest_for_task(task_id)
        next_version = 1 if previous is None else previous.context_version + 1

        snapshot = TaskContextSnapshot(
            task_id=task_id,
            scope_id=task_context.scope_id,
            context_version=next_version,
            resolved_context={
                "context": list(resolved.selected_context),
                "memories": [memory.to_dict() for memory in resolved.selected_memories],
            },
            provenance=tuple(resolved.provenance),
        )
        return self.store.save(snapshot)

    def get(self, snapshot_id: str) -> TaskContextSnapshot:
        """The immutable snapshot recorded as snapshot_id.

        Raises:
            UnknownTaskContextSnapshotError: If snapshot_id was never created
        """
        snapshot = self.store.get(snapshot_id)
        if snapshot is None:
            raise UnknownTaskContextSnapshotError(snapshot_id)
        return snapshot

    def list(self, task_id: str) -> list:
        """Every snapshot ever recorded for task_id, oldest (context_version 1) first."""
        return self.store.list_for_task(task_id)

    def restore(self, task_id: str, snapshot_id: str) -> LLMAgentTaskContext:
        """Restore task_id's own relevant_context/provenance to match
        snapshot_id's resolved_context["context"] -- a new task-context
        state (Commit #1's own updated_at/provenance trail moves
        forward), never a rewrite of the historical snapshot itself,
        which stays exactly as recorded. A fresh TaskContextSnapshot of
        the resulting state is recorded too (Rule/Test: "restore creates
        a new version"), so restoration is itself part of task_id's own
        snapshot history from here on.

        Raises:
            UnknownTaskContextSnapshotError: If snapshot_id was never created
            CrossTaskSnapshotError: If snapshot_id belongs to a task
                other than task_id
            UnknownTaskContextError: If task_id was never created
                (propagated from Commit #1's own get()/update(), unwrapped)
        """
        snapshot = self.get(snapshot_id)
        if snapshot.task_id != task_id:
            raise CrossTaskSnapshotError(
                f"snapshot {snapshot_id!r} belongs to task {snapshot.task_id!r}, not {task_id!r}"
            )

        self._task_context_service.get(task_id)  # confirms task_id itself still exists

        restored_context = list(snapshot.resolved_context.get("context", []))
        updated_task_context = self._task_context_service.update(
            task_id,
            {"relevant_context": restored_context, "provenance": list(snapshot.provenance)},
        )

        self.create(task_id)

        return updated_task_context
