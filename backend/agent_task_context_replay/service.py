from types import SimpleNamespace

from backend.agent_task_context import LLMAgentTaskContextService
from backend.agent_task_context_integrity import (
    InvalidContextIntegrityError,
    LLMAgentTaskContextIntegrityService,
)
from backend.agent_task_context_packaging import AgentContextPackage
from backend.agent_task_context_snapshots import LLMAgentTaskContextSnapshotService
from backend.llm.context_injection import CONTEXT_ROLE
from backend.llm.context_selection import content_text

from .models import TaskContextReplayResult


class InvalidContextReplayError(ValueError):
    """Raised when replay() is given a missing/blank task_id or snapshot_id."""


class CrossTaskReplayError(ValueError):
    """Raised when snapshot_id belongs to a task other than task_id."""


class LLMAgentTaskContextReplayService:
    """Reconstructs the exact context one historical TaskContextSnapshot
    (Commit #10) captured, purely for inspection -- never for execution.

    Not a second execution/replay framework: replay() never calls an LLM,
    never runs a capability, and never asks Commit #2's resolver (or any
    other live retrieval/selection path) for anything -- context and
    provenance come exclusively from Commit #10's own persisted
    TaskContextSnapshot (via LLMAgentTaskContextSnapshotService.get(),
    unchanged). Verifying the reconstructed context reuses Commit #5's
    own backend.agent_task_context_integrity.
    LLMAgentTaskContextIntegrityService.validate() -- the same
    provenance-shape, message-shape, and secret-content checks that
    already gate a live AgentContextPackage before it reaches an agent --
    applied here to a package assembled purely from the snapshot's own
    historical data. The task's own *current* agent_id/objective/
    constraints/inputs (immutable task identity/framing, per Commit #1 --
    never itself part of "historical context data") are used only to
    complete that package's required shape; the actual context/provenance
    payload validated is exclusively the snapshot's own.

    replay() only ever reads: LLMAgentTaskContextSnapshotService.get(),
    LLMAgentTaskContextService.get(), and LLMAgentTaskContextIntegrityService.
    validate() (itself read-only). Nothing here writes to, mutates, or
    executes anything -- not the task context, not a project context or
    memory store, and not an LLM.
    """

    def __init__(
        self,
        task_context_service: LLMAgentTaskContextService,
        snapshot_service: LLMAgentTaskContextSnapshotService,
        integrity_service: LLMAgentTaskContextIntegrityService = None,
    ):
        self._task_context_service = task_context_service
        self._snapshot_service = snapshot_service
        self._integrity_service = integrity_service or LLMAgentTaskContextIntegrityService()

    def replay(self, task_id: str, snapshot_id: str) -> TaskContextReplayResult:
        """Reconstruct snapshot_id's own historical context for task_id.

        Raises:
            InvalidContextReplayError: If task_id or snapshot_id is
                missing/blank
            UnknownTaskContextError: If task_id was never created
                (propagated from Commit #1's own get(), unwrapped --
                checked before snapshot_id, so an unknown task_id is
                never masked as a cross-task mismatch)
            UnknownTaskContextSnapshotError: If snapshot_id was never
                created (propagated from Commit #10's own get(), unwrapped)
            CrossTaskReplayError: If snapshot_id belongs to a different task
        """
        self._validate(task_id, snapshot_id)

        task_context = self._task_context_service.get(task_id)

        snapshot = self._snapshot_service.get(snapshot_id)
        if snapshot.task_id != task_id:
            raise CrossTaskReplayError(
                f"snapshot {snapshot_id!r} belongs to task {snapshot.task_id!r}, not {task_id!r}"
            )

        differences = []

        resolved_context = snapshot.resolved_context if isinstance(snapshot.resolved_context, dict) else {}
        if "context" not in resolved_context:
            differences.append(
                f"snapshot {snapshot_id!r} carries no resolved_context['context'] at all -- cannot reconstruct"
            )
        context = [entry for entry in resolved_context.get("context", []) if isinstance(entry, dict)]
        memories = [entry for entry in resolved_context.get("memories", []) if isinstance(entry, dict)]

        provenance = list(snapshot.provenance)

        package = self._package_from_snapshot(snapshot, task_context, context, memories)
        try:
            integrity_result = self._integrity_service.validate(package, task_context.agent_id, snapshot.scope_id)
            differences.extend(integrity_result.errors)
        except InvalidContextIntegrityError as error:
            differences.append(f"snapshot {snapshot_id!r} could not be validated: {error}")

        return TaskContextReplayResult(
            snapshot_id=snapshot_id,
            task_id=task_id,
            context_version=snapshot.context_version,
            context=context,
            provenance=provenance,
            reproducible=not differences,
            differences=differences,
        )

    # -- internals ------------------------------------------------------------

    @staticmethod
    def _package_from_snapshot(snapshot, task_context, context, memories) -> AgentContextPackage:
        provenance_by_id = {}
        for record in snapshot.provenance:
            provenance_by_id[record.context_id] = record  # last (most recent) wins

        context_messages = []
        for entry in context:
            context_id = entry.get("context_id")
            message_metadata = {
                "context_id": context_id,
                "scope_id": entry.get("scope_id"),
                "context_type": entry.get("context_type"),
            }
            provenance = provenance_by_id.get(context_id)
            if provenance is not None:
                message_metadata["provenance"] = {
                    "source_type": provenance.source_type,
                    "source_id": provenance.source_id,
                    "source_version": provenance.source_version,
                    "excerpt": provenance.excerpt,
                }
            context_messages.append(
                {
                    "role": CONTEXT_ROLE,
                    "content": content_text(SimpleNamespace(content=entry.get("content"))),
                    "metadata": message_metadata,
                }
            )

        return AgentContextPackage(
            task={
                "task_id": snapshot.task_id,
                "agent_id": task_context.agent_id,
                "scope_id": snapshot.scope_id,
                "objective": task_context.objective,
                "inputs": dict(task_context.inputs),
            },
            constraints=list(task_context.constraints),
            context=context_messages,
            memories=memories,
            provenance=list(snapshot.provenance),
            metadata={},
        )

    @staticmethod
    def _validate(task_id, snapshot_id) -> None:
        if not task_id or not isinstance(task_id, str):
            raise InvalidContextReplayError("task_id is required and must be a non-empty string")
        if not snapshot_id or not isinstance(snapshot_id, str):
            raise InvalidContextReplayError("snapshot_id is required and must be a non-empty string")
