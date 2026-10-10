import json
from copy import deepcopy
from datetime import datetime
from types import MappingProxyType

from backend.llm.context_compaction import LLMContextCompactionService
from backend.llm.context_provenance import VALID_SOURCE_TYPES, LLMContextProvenance
from backend.llm.context_selection import LLMContextSelectionService
from backend.llm.project_context import LLMProjectContext

from .in_memory_store import InMemoryTaskContextStore
from .models import DEFAULT_TASK_CONTEXT_TOKEN_BUDGET, LLMAgentTaskContext, LLMAgentTaskContextSnapshot
from .store import TaskContextStore

# Fields update() may change. Identity (task_id/agent_id/scope_id) and
# timestamps are never accepted here -- a task context stays bound to the
# (task, agent, scope) it was created for, and updated_at is always the
# store's own doing (see TaskContextStore.save()).
_UPDATABLE_FIELDS = frozenset({"objective", "constraints", "inputs", "relevant_context", "provenance"})
_IMMUTABLE_FIELDS = frozenset({"task_id", "agent_id", "scope_id", "created_at", "updated_at"})


class UnknownTaskContextError(KeyError):
    """Raised when get()/update()/snapshot() is given a task_id that was never created."""


class InvalidTaskContextError(ValueError):
    """Raised when a task context's own fields, or update()'s changes, fail validation."""


class LLMAgentTaskContextService:
    """Creates, reads, and updates the canonical task-context record an
    agent's execution works from.

    This is deliberately not a second context or memory engine:
    select_relevant_context() reuses backend.llm.context_selection.
    LLMContextSelectionService (relevance ranking) and backend.llm.
    context_compaction.LLMContextCompactionService (budget fitting)
    verbatim to turn a pool of already-durable backend.llm.project_context.
    LLMProjectContext candidates into a task's relevant_context, and every
    provenance record this service writes is a plain
    backend.llm.context_provenance.LLMContextProvenance -- the repository's
    own existing "where did this context come from" primitive, reused
    as-is rather than reinvented for tasks specifically. Nothing here
    executes a capability or produces a plan; a task context is inert,
    structured input for whatever downstream service does that.
    """

    def __init__(
        self,
        store: TaskContextStore = None,
        context_selection: LLMContextSelectionService = None,
        context_compaction: LLMContextCompactionService = None,
    ):
        self.store = store if store is not None else InMemoryTaskContextStore()
        self._context_selection = context_selection or LLMContextSelectionService()
        self._context_compaction = context_compaction or LLMContextCompactionService()

    def create(
        self,
        agent_id: str,
        scope_id: str,
        objective: str,
        constraints: list = None,
        inputs: dict = None,
        relevant_context: list = None,
        provenance: list = None,
        task_id: str = None,
    ) -> LLMAgentTaskContext:
        """Record a new task context for one (agent_id, scope_id) pair.

        relevant_context/provenance may be supplied directly (e.g. built
        via select_relevant_context()); any relevant_context entry that
        carries its own context_id and has no matching provenance entry
        yet gets one derived automatically (Rule: "preserve provenance
        for injected context" applies from the very first save, not only
        on later updates).

        Raises:
            InvalidTaskContextError: If agent_id, scope_id, objective,
                constraints, inputs, relevant_context, provenance, or an
                explicitly given task_id fails validation
        """
        self._validate_identity(agent_id, scope_id, objective)
        resolved_constraints = self._validate_constraints(constraints)
        resolved_inputs = self._validate_inputs(inputs)
        resolved_context = self._validate_relevant_context(relevant_context)
        resolved_provenance = self._validate_provenance(provenance)
        resolved_provenance = resolved_provenance + self._derive_provenance(resolved_context, resolved_provenance)

        kwargs = dict(
            agent_id=agent_id,
            scope_id=scope_id,
            objective=objective,
            constraints=resolved_constraints,
            inputs=resolved_inputs,
            relevant_context=resolved_context,
            provenance=resolved_provenance,
        )
        if task_id is not None:
            if not isinstance(task_id, str) or not task_id.strip():
                raise InvalidTaskContextError("task_id must be a non-empty string when given")
            kwargs["task_id"] = task_id

        return self.store.save(LLMAgentTaskContext(**kwargs))

    def get(self, task_id: str) -> LLMAgentTaskContext:
        """The current task context for task_id.

        Raises:
            UnknownTaskContextError: If task_id was never created
        """
        task_context = self.store.get(task_id)
        if task_context is None:
            raise UnknownTaskContextError(task_id)
        return task_context

    def update(self, task_id: str, changes: dict) -> LLMAgentTaskContext:
        """Apply changes to an existing task context. Fields not named in
        changes are left exactly as they were (Rule: "updates must not
        silently erase existing context").

        changes may set objective/constraints/inputs/relevant_context/
        provenance. provenance is append-only: any entries given in
        changes["provenance"], plus any auto-derived from a new
        changes["relevant_context"], are added to the existing trail --
        never replace it -- so context dropped from the current
        relevant_context is still traceable afterward.

        Raises:
            UnknownTaskContextError: If task_id was never created
            InvalidTaskContextError: If changes is not a dict, names an
                identity/timestamp field, names an unknown field, or a
                given field's new value fails validation
        """
        if not isinstance(changes, dict):
            raise InvalidTaskContextError("changes must be a dict")

        given = set(changes)
        immutable_given = given & _IMMUTABLE_FIELDS
        if immutable_given:
            raise InvalidTaskContextError(
                f"cannot change identity/timestamp fields via update(): {sorted(immutable_given)}"
            )
        unknown = given - _UPDATABLE_FIELDS - _IMMUTABLE_FIELDS
        if unknown:
            raise InvalidTaskContextError(f"unknown field(s) in changes: {sorted(unknown)}")

        task_context = self.get(task_id)

        if "objective" in changes:
            objective = changes["objective"]
            if not objective or not isinstance(objective, str):
                raise InvalidTaskContextError("objective must be a non-empty string")
            task_context.objective = objective

        if "constraints" in changes:
            task_context.constraints = self._validate_constraints(changes["constraints"])

        if "inputs" in changes:
            task_context.inputs = self._validate_inputs(changes["inputs"])

        new_provenance = []
        if "relevant_context" in changes:
            resolved_context = self._validate_relevant_context(changes["relevant_context"])
            task_context.relevant_context = resolved_context
            new_provenance.extend(self._derive_provenance(resolved_context, task_context.provenance))

        if "provenance" in changes:
            new_provenance.extend(self._validate_provenance(changes["provenance"]))

        if new_provenance:
            task_context.provenance = task_context.provenance + new_provenance

        return self.store.save(task_context)

    def snapshot(self, task_id: str) -> LLMAgentTaskContextSnapshot:
        """An immutable, point-in-time copy of task_id's current task context.

        Taken now: a later update() to the live task context never
        changes a snapshot already returned (Rule: "snapshots are
        immutable").

        Raises:
            UnknownTaskContextError: If task_id was never created
        """
        task_context = self.get(task_id)
        return LLMAgentTaskContextSnapshot(
            task_id=task_context.task_id,
            agent_id=task_context.agent_id,
            scope_id=task_context.scope_id,
            objective=task_context.objective,
            constraints=tuple(deepcopy(task_context.constraints)),
            inputs=MappingProxyType(deepcopy(task_context.inputs)),
            relevant_context=tuple(deepcopy(task_context.relevant_context)),
            provenance=tuple(task_context.provenance),
            created_at=task_context.created_at,
            updated_at=task_context.updated_at,
        )

    def select_relevant_context(self, candidates: list, objective: str, token_budget: int = None) -> list:
        """Rank and budget-fit candidates (LLMProjectContext) for objective.

        Reuses backend.llm.context_selection.LLMContextSelectionService for
        relevance ranking and backend.llm.context_compaction.
        LLMContextCompactionService to fit the result under token_budget --
        no second relevance or token-budget mechanism. The result is ready
        to pass straight to create()/update() as relevant_context.
        """
        budget = token_budget if token_budget is not None else DEFAULT_TASK_CONTEXT_TOKEN_BUDGET
        selected = self._context_selection.select(list(candidates), objective, budget)
        compacted = self._context_compaction.compact(selected, budget)
        return [entry.to_dict() for entry in compacted]

    def _derive_provenance(self, relevant_context: list, existing_provenance: list) -> list:
        """One LLMContextProvenance per new relevant_context entry that
        names its own context_id and has no provenance record yet --
        idempotent across repeated updates with the same entries."""
        known_ids = {entry.context_id for entry in existing_provenance}
        derived = []
        for entry in relevant_context:
            context_id = entry.get("context_id")
            if not context_id or context_id in known_ids:
                continue
            derived.append(
                LLMContextProvenance(
                    context_id=context_id,
                    source_type="project_context" if entry.get("context_type") else "external",
                    source_id=context_id,
                    excerpt=self._excerpt(entry.get("content")),
                )
            )
            known_ids.add(context_id)
        return derived

    @staticmethod
    def _excerpt(content) -> str:
        text = content if isinstance(content, str) else json.dumps(content, sort_keys=True, default=str)
        text = text.strip()
        return (text[:200] if text else "(no content)")

    @staticmethod
    def _validate_identity(agent_id, scope_id, objective) -> None:
        if not agent_id or not isinstance(agent_id, str):
            raise InvalidTaskContextError("agent_id is required and must be a non-empty string")
        if not scope_id or not isinstance(scope_id, str):
            raise InvalidTaskContextError("scope_id is required and must identify a project/notebook/API")
        if not objective or not isinstance(objective, str):
            raise InvalidTaskContextError("objective is required and must be a non-empty string")

    @staticmethod
    def _validate_constraints(constraints) -> list:
        if constraints is None:
            return []
        if not isinstance(constraints, list):
            raise InvalidTaskContextError("constraints must be a list")
        return list(constraints)

    @staticmethod
    def _validate_inputs(inputs) -> dict:
        if inputs is None:
            return {}
        if not isinstance(inputs, dict):
            raise InvalidTaskContextError("inputs must be a dict")
        return dict(inputs)

    @staticmethod
    def _validate_relevant_context(relevant_context) -> list:
        if relevant_context is None:
            return []
        if not isinstance(relevant_context, list):
            raise InvalidTaskContextError("relevant_context must be a list")

        resolved = []
        for entry in relevant_context:
            if isinstance(entry, LLMProjectContext):
                resolved.append(entry.to_dict())
            elif isinstance(entry, dict):
                resolved.append(dict(entry))
            else:
                raise InvalidTaskContextError(
                    f"each relevant_context entry must be an LLMProjectContext or dict, "
                    f"got {type(entry).__name__}"
                )
        return resolved

    @classmethod
    def _validate_provenance(cls, provenance) -> list:
        if provenance is None:
            return []
        if not isinstance(provenance, list):
            raise InvalidTaskContextError("provenance must be a list")
        return [cls._validate_provenance_entry(entry) for entry in provenance]

    @staticmethod
    def _validate_provenance_entry(entry) -> LLMContextProvenance:
        if isinstance(entry, LLMContextProvenance):
            return entry
        if not isinstance(entry, dict):
            raise InvalidTaskContextError(
                f"each provenance entry must be an LLMContextProvenance or dict, got {type(entry).__name__}"
            )

        for field_name in ("context_id", "source_id", "excerpt"):
            if not entry.get(field_name) or not isinstance(entry.get(field_name), str):
                raise InvalidTaskContextError(f"provenance entry is missing a valid {field_name!r}")

        source_type = entry.get("source_type")
        if source_type not in VALID_SOURCE_TYPES:
            raise InvalidTaskContextError(
                f"provenance source_type {source_type!r} is not one of {sorted(VALID_SOURCE_TYPES)}"
            )

        source_version = entry.get("source_version")
        if source_version is not None and (
            isinstance(source_version, bool) or not isinstance(source_version, int) or source_version < 1
        ):
            raise InvalidTaskContextError("provenance source_version must be a positive integer when present")

        kwargs = dict(
            context_id=entry["context_id"],
            source_type=source_type,
            source_id=entry["source_id"],
            excerpt=entry["excerpt"],
            source_version=source_version,
        )
        created_at = entry.get("created_at")
        if isinstance(created_at, str):
            kwargs["created_at"] = datetime.fromisoformat(created_at)
        elif isinstance(created_at, datetime):
            kwargs["created_at"] = created_at
        if entry.get("provenance_id"):
            kwargs["provenance_id"] = entry["provenance_id"]

        return LLMContextProvenance(**kwargs)
