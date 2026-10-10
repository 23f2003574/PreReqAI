import json

from backend.agent_execution_memory import LLMAgentMemoryService
from backend.agent_memory_retrieval import LLMAgentMemoryQuery, LLMAgentMemoryRetriever
from backend.agent_policy_engine import DENY, LLMAgentPolicyEvaluator
from backend.agent_policy_resolution import LLMAgentPolicyResolver
from backend.agent_task_context import DEFAULT_TASK_CONTEXT_TOKEN_BUDGET, LLMAgentTaskContextService
from backend.llm.context_compaction import LLMContextCompactionService
from backend.llm.context_freshness import LLMContextFreshnessService
from backend.llm.context_provenance import LLMContextProvenance
from backend.llm.context_retrieval import LLMContextRetrievalService
from backend.llm.context_selection import LLMContextSelectionService
from backend.llm.project_context import LLMProjectContextService

from .models import ResolvedAgentTaskContext

DEFAULT_MEMORY_LIMIT = 5


class InvalidTaskContextResolutionError(ValueError):
    """Raised when resolve() is given a missing/blank agent_id or scope_id."""


class TaskContextScopeMismatchError(ValueError):
    """Raised when task_id's own agent_id/scope_id does not match the
    agent_id/scope_id resolve() was called with -- a caller can only
    resolve a task context for the agent/scope it actually belongs to."""


class LLMAgentTaskContextResolver:
    """Deterministically resolves the final context one agent should
    receive for one task, combining Commit #1's own explicit task context
    with whatever the repository's existing project-context and
    agent-memory systems can add.

    Not a second retrieval, ranking, or memory system: additional project
    context is discovered via backend.llm.context_retrieval.
    LLMContextRetrievalService.rank() (the repository's one deterministic,
    embedding-free keyword-overlap ranker over
    backend.llm.project_context.LLMProjectContextService.list(scope_id) --
    already scope-isolated), then fit to a budget with the exact same
    backend.llm.context_selection.LLMContextSelectionService/backend.llm.
    context_compaction.LLMContextCompactionService pair Commit #1's own
    select_relevant_context() reuses. Memory is
    backend.agent_memory_retrieval.LLMAgentMemoryRetriever.retrieve(),
    unchanged -- already scope-isolated via backend.agent_execution_memory.
    LLMAgentMemoryService.list(). Authorization (when a policy_service is
    given) is the exact backend.agent_policy_engine/backend.
    agent_policy_resolution pair backend.agent_capability_resolution.
    LLMAgentCapabilityResolver already reuses for the same "explicit deny
    always wins, absence of any policy restricts nothing" default
    posture. Staleness (when a freshness_service is given) is backend.llm.
    context_freshness.LLMContextFreshnessService.stale(), unchanged.

    project_context_service, memory_service, policy_service, and
    freshness_service are all optional collaborators (the same duck-typed
    "used only if given" shape backend.llm.tool_permissions.
    LLMToolPermissionService.__init__'s own invocation_service already
    uses): omitting project_context_service/memory_service means no
    additional context/memory is pulled at all (the task's own explicit
    context is still returned in full); omitting policy_service/
    freshness_service means no candidate is ever excluded as unauthorized/
    stale.

    resolve() only ever reads: task_context_service.get(),
    project_context_service.list() (via rank()), memory_service.list()
    (via retrieve()), and whatever policy_service/freshness_service read
    internally -- nothing here creates, updates, or archives a task
    context, project context, or memory. The same (task_id, agent_id,
    scope_id, and current store/policy/freshness state) always resolves
    to the same ResolvedAgentTaskContext.
    """

    def __init__(
        self,
        task_context_service: LLMAgentTaskContextService,
        project_context_service: LLMProjectContextService = None,
        memory_service: LLMAgentMemoryService = None,
        policy_service=None,
        freshness_service: LLMContextFreshnessService = None,
        context_selection: LLMContextSelectionService = None,
        context_compaction: LLMContextCompactionService = None,
        token_budget: int = None,
        memory_limit: int = DEFAULT_MEMORY_LIMIT,
    ):
        self._task_context_service = task_context_service
        self._context_retrieval = (
            LLMContextRetrievalService(project_context_service) if project_context_service is not None else None
        )
        self._memory_retriever = LLMAgentMemoryRetriever(memory_service) if memory_service is not None else None
        self._policy_resolver = LLMAgentPolicyResolver(policy_service) if policy_service is not None else None
        self._policy_evaluator = LLMAgentPolicyEvaluator() if policy_service is not None else None
        self._freshness_service = freshness_service
        self._context_selection = context_selection or LLMContextSelectionService()
        self._context_compaction = context_compaction or LLMContextCompactionService()
        self._token_budget = token_budget or DEFAULT_TASK_CONTEXT_TOKEN_BUDGET
        self._memory_limit = memory_limit

    def resolve(self, task_id: str, agent_id: str, scope_id: str) -> ResolvedAgentTaskContext:
        """Resolve the final context agent_id should receive for task_id in scope_id.

        Raises:
            InvalidTaskContextResolutionError: If agent_id or scope_id is
                missing/blank
            UnknownTaskContextError: If task_id was never created
                (propagated from Commit #1's own get(), unwrapped)
            TaskContextScopeMismatchError: If task_id does not belong to
                agent_id in scope_id
        """
        self._validate_identifier(agent_id, "agent_id")
        self._validate_identifier(scope_id, "scope_id")

        task_context = self._task_context_service.get(task_id)
        if task_context.agent_id != agent_id or task_context.scope_id != scope_id:
            raise TaskContextScopeMismatchError(
                f"task {task_id!r} belongs to agent {task_context.agent_id!r} in scope "
                f"{task_context.scope_id!r}, not agent {agent_id!r} in scope {scope_id!r}"
            )

        # Rule: start with the task's own explicit context -- carried over
        # verbatim and unconditionally, never re-filtered by relevance,
        # staleness, or authorization.
        selected_context = [dict(entry) for entry in task_context.relevant_context]
        explicit_ids = {entry.get("context_id") for entry in task_context.relevant_context if entry.get("context_id")}
        provenance = list(task_context.provenance)
        reasons = {}
        if task_context.relevant_context:
            count = len(task_context.relevant_context)
            reasons["__task_context__"] = (
                f"{count} entr{'y' if count == 1 else 'ies'} carried verbatim from task {task_id!r}'s "
                "own explicit relevant_context"
            )

        excluded_context = []

        if self._context_retrieval is not None:
            included, excluded, new_provenance = self._resolve_project_context(
                agent_id, scope_id, task_id, task_context, explicit_ids, reasons
            )
            selected_context.extend(included)
            excluded_context.extend(excluded)
            provenance.extend(self._merge_provenance(new_provenance, provenance))

        selected_memories = []
        if self._memory_retriever is not None:
            selected_memories, memory_provenance = self._resolve_memories(scope_id, task_context, reasons)
            provenance.extend(self._merge_provenance(memory_provenance, provenance))

        return ResolvedAgentTaskContext(
            task_id=task_id,
            agent_id=agent_id,
            scope_id=scope_id,
            task_context=task_context,
            selected_context=selected_context,
            selected_memories=selected_memories,
            excluded_context=excluded_context,
            provenance=provenance,
            resolution_reasons=reasons,
        )

    # -- internals ------------------------------------------------------------

    def _resolve_project_context(self, agent_id, scope_id, task_id, task_context, explicit_ids, reasons):
        matches = self._context_retrieval.rank(scope_id, task_context.objective)

        excluded = []
        candidates = []
        for match in matches:
            candidate = match.context

            if candidate.context_id in explicit_ids:
                excluded.append(candidate.to_dict())
                reasons[candidate.context_id] = (
                    f"context {candidate.context_id!r} already present in task {task_id!r}'s own "
                    "explicit relevant_context"
                )
                continue

            denial = self._authorization_denial(agent_id, scope_id, candidate)
            if denial is not None:
                excluded.append(candidate.to_dict())
                reasons[candidate.context_id] = (
                    f"context {candidate.context_id!r} denied for agent {agent_id!r} in scope "
                    f"{scope_id!r} by policy {denial.policy_id!r} rule {denial.rule_id!r}: {denial.reason}"
                )
                continue

            if self._freshness_service is not None and self._freshness_service.stale(candidate.context_id):
                freshness = self._freshness_service.check(candidate.context_id)
                excluded.append(candidate.to_dict())
                reasons[candidate.context_id] = f"context {candidate.context_id!r} excluded as stale: {freshness.reason}"
                continue

            # score_context()'s own convention: 0.0 means no query term matched
            # at all -- the natural, non-arbitrary cut point for "irrelevant",
            # checked before compaction so a zero-relevance item is never kept
            # merely because it happens to fit the token budget.
            if match.score <= 0.0:
                excluded.append(candidate.to_dict())
                reasons[candidate.context_id] = (
                    f"context {candidate.context_id!r} excluded as irrelevant: {match.reason}"
                )
                continue

            candidates.append((candidate, match.score, match.reason))

        candidate_contexts = [candidate for candidate, _score, _reason in candidates]
        selected = self._context_selection.select(candidate_contexts, task_context.objective, self._token_budget)
        selected = self._context_compaction.compact(selected, self._token_budget)
        selected_ids = {context.context_id for context in selected}
        score_by_id = {candidate.context_id: (score, reason) for candidate, score, reason in candidates}

        included = []
        for context in selected:
            included.append(context.to_dict())
            score, match_reason = score_by_id.get(context.context_id, (None, ""))
            reasons[context.context_id] = (
                f"context {context.context_id!r} included: relevance score {score} ({match_reason})"
            )

        for candidate, score, match_reason in candidates:
            if candidate.context_id in selected_ids:
                continue
            excluded.append(candidate.to_dict())
            reasons[candidate.context_id] = (
                f"context {candidate.context_id!r} excluded: did not fit the token budget "
                f"(relevance score {score}, {match_reason})"
            )

        new_provenance = [
            LLMContextProvenance(
                context_id=entry["context_id"],
                source_type="project_context",
                source_id=entry["context_id"],
                excerpt=self._excerpt(entry.get("content")),
            )
            for entry in included
            if entry.get("context_id")
        ]
        return included, excluded, new_provenance

    def _resolve_memories(self, scope_id, task_context, reasons):
        query = LLMAgentMemoryQuery(scope_id=scope_id, query=task_context.objective, limit=self._memory_limit)
        memories = self._memory_retriever.retrieve(query)

        for memory in memories:
            reasons[memory.memory_id] = (
                f"memory {memory.memory_id!r} included as relevant execution memory "
                f"(memory_type={memory.memory_type!r}, outcome={memory.outcome!r})"
            )

        new_provenance = [
            LLMContextProvenance(
                context_id=memory.memory_id,
                source_type="agent_memory",
                source_id=memory.memory_id,
                excerpt=self._excerpt(memory.content),
            )
            for memory in memories
        ]
        return memories, new_provenance

    def _authorization_denial(self, agent_id, scope_id, candidate):
        """The first policy decision (in precedence order) that explicitly
        denies candidate to agent_id -- None when policy_service was not
        supplied, or nothing explicitly denies it. Mirrors
        backend.agent_capability_resolution.LLMAgentCapabilityResolver.
        _first_explicit_denial() exactly."""
        if self._policy_resolver is None:
            return None

        action = {
            "agent_id": agent_id,
            "scope_id": scope_id,
            "context_id": candidate.context_id,
            "context_type": candidate.context_type,
        }
        for resolved in self._policy_resolver.resolve(scope_id):
            decision = self._policy_evaluator.evaluate(resolved.policy, action)
            if decision.rule_id is not None and decision.effect == DENY:
                return decision
        return None

    @staticmethod
    def _merge_provenance(new_entries: list, existing: list) -> list:
        """new_entries not already covered by an existing record with the
        same context_id -- keeps provenance idempotent across repeated
        resolutions, the same discipline Commit #1's own
        LLMAgentTaskContextService._derive_provenance() already applies."""
        known_ids = {entry.context_id for entry in existing}
        merged = []
        for entry in new_entries:
            if entry.context_id in known_ids:
                continue
            merged.append(entry)
            known_ids.add(entry.context_id)
        return merged

    @staticmethod
    def _excerpt(content) -> str:
        text = content if isinstance(content, str) else json.dumps(content, sort_keys=True, default=str)
        text = text.strip()
        return text[:200] if text else "(no content)"

    @staticmethod
    def _validate_identifier(value, field_name):
        if not value or not isinstance(value, str):
            raise InvalidTaskContextResolutionError(f"{field_name} is required and must be a non-empty string")
