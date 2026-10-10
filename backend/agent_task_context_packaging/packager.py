from dataclasses import asdict
from datetime import datetime
from types import SimpleNamespace

from backend.agent_task_context import LLMAgentTaskContext
from backend.agent_task_context_budgeting import BudgetedAgentTaskContext
from backend.llm.context_injection import CONTEXT_ROLE
from backend.llm.context_selection import content_text

from .models import AgentContextPackage


class InvalidContextPackageError(ValueError):
    """Raised when package() is given the wrong types, or a task_context/
    budgeted_context pair that do not identify the same task."""


class LLMAgentTaskContextPackager:
    """Assembles the final, request-ready context package from one
    budgeted task context.

    Not a second prompt or provider abstraction: context entries are
    rendered in the exact {"role", "content", "metadata"} envelope
    backend.llm.context_injection.LLMContextInjectionService._message_for()
    already establishes for injecting project context into a real
    LLMRequest, using the same CONTEXT_ROLE constant and the same
    content_text() rendering backend.llm.context_selection already uses
    for token sizing -- so this service's own output can be folded
    straight into LLMRequest.messages the way inject() already does.
    Provenance is sourced from Commit #3's own already-computed
    provenance list, not a live LLMContextProvenanceService lookup
    (nothing here calls out to a store).

    package() only ever reads the LLMAgentTaskContext and
    BudgetedAgentTaskContext it is given -- it never calls a task
    context, project context, or memory service, and never mutates
    either argument. The same (task_context, budgeted_context,
    request_context) always package to the same AgentContextPackage; no
    field here is derived from the wall clock.
    """

    def package(
        self,
        task_context: LLMAgentTaskContext,
        budgeted_context: BudgetedAgentTaskContext,
        request_context: dict = None,
    ) -> AgentContextPackage:
        """Package task_context/budgeted_context into an AgentContextPackage.

        Raises:
            InvalidContextPackageError: If task_context is not an
                LLMAgentTaskContext, budgeted_context is not a
                BudgetedAgentTaskContext, the two do not share the same
                task_id/agent_id/scope_id, or request_context is given
                and is not a dict
        """
        self._validate(task_context, budgeted_context, request_context)

        task = {
            "task_id": task_context.task_id,
            "agent_id": task_context.agent_id,
            "scope_id": task_context.scope_id,
            "objective": task_context.objective,
            "inputs": dict(task_context.inputs),
        }
        constraints = list(task_context.constraints)

        provenance_by_id = {}
        for record in budgeted_context.provenance:
            provenance_by_id[record.context_id] = record  # last (most recent) wins

        context = [self._message_for(entry, provenance_by_id) for entry in budgeted_context.selected_context]

        memories = [memory.to_dict() for memory in budgeted_context.selected_memories]

        provenance = [self._provenance_to_dict(entry) for entry in budgeted_context.provenance]

        metadata = {
            "task_id": task_context.task_id,
            "agent_id": task_context.agent_id,
            "scope_id": task_context.scope_id,
            "budget": budgeted_context.budget,
            "estimated_tokens": budgeted_context.estimated_tokens,
            "truncation_applied": budgeted_context.truncation_applied,
        }
        if request_context:
            metadata["request_context"] = dict(request_context)

        return AgentContextPackage(
            task=task,
            constraints=constraints,
            context=context,
            memories=memories,
            provenance=provenance,
            metadata=metadata,
        )

    @staticmethod
    def _message_for(entry: dict, provenance_by_id: dict) -> dict:
        message_metadata = {
            "context_id": entry.get("context_id"),
            "scope_id": entry.get("scope_id"),
            "context_type": entry.get("context_type"),
        }
        provenance = provenance_by_id.get(entry.get("context_id"))
        if provenance is not None:
            message_metadata["provenance"] = LLMAgentTaskContextPackager._provenance_to_dict(provenance)

        return {
            "role": CONTEXT_ROLE,
            "content": content_text(SimpleNamespace(content=entry.get("content"))),
            "metadata": message_metadata,
        }

    @staticmethod
    def _provenance_to_dict(entry) -> dict:
        data = asdict(entry)
        if isinstance(data.get("created_at"), datetime):
            data["created_at"] = data["created_at"].isoformat()
        return data

    @staticmethod
    def _validate(task_context, budgeted_context, request_context) -> None:
        if not isinstance(task_context, LLMAgentTaskContext):
            raise InvalidContextPackageError(
                f"task_context must be an LLMAgentTaskContext, got {type(task_context).__name__}"
            )
        if not isinstance(budgeted_context, BudgetedAgentTaskContext):
            raise InvalidContextPackageError(
                f"budgeted_context must be a BudgetedAgentTaskContext, got {type(budgeted_context).__name__}"
            )
        if (
            task_context.task_id != budgeted_context.task_id
            or task_context.agent_id != budgeted_context.agent_id
            or task_context.scope_id != budgeted_context.scope_id
        ):
            raise InvalidContextPackageError(
                f"task_context {task_context.task_id!r} does not match budgeted_context "
                f"{budgeted_context.task_id!r} (agent/scope must agree too)"
            )
        if request_context is not None and not isinstance(request_context, dict):
            raise InvalidContextPackageError("request_context must be a dict when given")
