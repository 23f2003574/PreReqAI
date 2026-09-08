from backend.agent_capability_compatibility import LLMAgentCapabilityCompatibility
from backend.agent_capability_registry import LLMAgentCapabilityRegistry
from backend.agent_capability_resolution import LLMAgentCapabilityResolver
from backend.llm.context_retrieval import searchable_text, tokenize

from .models import CapabilitySelectionResult


def score_capability(capability, task_context: dict) -> float:
    """Deterministic keyword-overlap relevance of one capability to
    task_context.

    Reuses backend.llm.context_retrieval's own tokenize()/searchable_text()
    -- the exact case-insensitive token-overlap convention
    backend.agent_strategy_retrieval.score_strategy() and
    backend.agent_memory_retrieval's own score_memory() already reuse for
    two other unrelated domains -- rather than a second relevance system.
    task_context is rendered as one searchable blob the same way
    backend.llm.context_retrieval.score_context() already renders a
    structured metadata dict, so a caller's task_context needs no fixed
    "query" field of its own: every value anywhere in it contributes to
    the match.
    """
    query_tokens = set(tokenize(searchable_text(task_context)))
    if not query_tokens:
        return 0.0

    haystack = (
        set(tokenize(searchable_text(capability.name)))
        | set(tokenize(searchable_text(capability.description)))
        | set(tokenize(searchable_text(capability.category)))
    )
    matched = query_tokens & haystack
    return round(len(matched) / len(query_tokens), 6)


class InvalidCapabilitySelectionError(ValueError):
    """Raised when select() is given a missing/blank agent_id/scope_id, a
    task_context that is not a dict, or a candidates argument that is
    not a list of non-empty strings."""


class LLMAgentCapabilitySelector:
    """Deterministically selects the best usable Commit #1 capabilities
    for one agent task, from everything this series has already built --
    never a second planner, scorer, or compatibility/permission engine.

    Candidate discovery is entirely Commit #2's own
    LLMAgentCapabilityResolver.resolve() (Rule: "start from resolved
    capabilities unless explicit candidates are supplied") -- archived
    and policy-excluded capabilities never even become candidates in
    that path. Every candidate, whichever way it was discovered, is then
    checked with Commit #5's own LLMAgentCapabilityCompatibility.check()
    (which itself already composes Commit #1/#2/#3/#4 -- registry
    existence/availability, contract presence and required context,
    and dependency satisfiability) -- never a second copy of any of
    those checks, and never re-validated some other way.

    Ranking among compatible candidates reuses
    backend.llm.context_retrieval's own tokenize()/searchable_text()
    keyword-overlap primitive (score_capability(), above) -- the
    repository's one deterministic, embedding-free relevance scorer,
    the same one backend.agent_strategy_selection.LLMAgentStrategySelector
    already reuses for an unrelated domain's own selection. Ties break by
    most-recently-registered capability first, then by capability_id --
    the exact same deterministic tie-break
    backend.agent_strategy_selection.LLMAgentStrategySelector.select()
    already uses, so repeated calls over the same state always return
    the same order.

    select() only ever reads (LLMAgentCapabilityResolver.resolve(),
    LLMAgentCapabilityCompatibility.check(),
    LLMAgentCapabilityRegistry.get()) -- no capability, contract,
    dependency, or policy is ever created, changed, or removed by
    selecting from it, no capability is executed, and no agent state is
    touched. This is advisory input for whatever assembles a plan, never
    a replacement for backend.agent_task_planning.LLMAgentPlanningService
    itself, which this class never calls and which remains entirely
    authoritative over the plan it actually produces.
    """

    def __init__(
        self,
        capability_registry: LLMAgentCapabilityRegistry,
        capability_resolver: LLMAgentCapabilityResolver,
        compatibility: LLMAgentCapabilityCompatibility,
    ):
        self._capability_registry = capability_registry
        self._capability_resolver = capability_resolver
        self._compatibility = compatibility

    def select(
        self, agent_id: str, scope_id: str, task_context: dict, candidates: list = None
    ) -> CapabilitySelectionResult:
        """Select the best usable capabilities for agent_id in scope_id
        given task_context, best first.

        candidates, when given, replaces resolution as the candidate
        source (Rule: "start from resolved capabilities unless explicit
        candidates are supplied") -- but every candidate, from either
        source, still goes through the exact same
        LLMAgentCapabilityCompatibility.check(), so an incompatible
        explicitly-named candidate is rejected exactly as it would be if
        discovered through resolution.

        Raises:
            InvalidCapabilitySelectionError: If agent_id/scope_id is
                missing or blank, task_context is not a dict, or
                candidates is given and is not a list of non-empty
                strings
            InvalidCapabilityResolutionError: Propagated unchanged from
                LLMAgentCapabilityResolver.resolve() when candidates is
                None
        """
        self._validate_id(agent_id, "agent_id")
        self._validate_id(scope_id, "scope_id")
        if not isinstance(task_context, dict):
            raise InvalidCapabilitySelectionError(
                f"task_context must be a dict, got {type(task_context).__name__}"
            )

        if candidates is None:
            resolved = self._capability_resolver.resolve(agent_id, scope_id, task_context)
            candidate_ids = [capability.capability_id for capability in resolved.capabilities]
        else:
            if not isinstance(candidates, list) or not all(
                isinstance(candidate, str) and candidate for candidate in candidates
            ):
                raise InvalidCapabilitySelectionError("candidates must be a list of non-empty strings")
            candidate_ids = list(candidates)

        reasons = {}
        rejected = []
        ranked = []

        for capability_id in candidate_ids:
            result = self._compatibility.check(capability_id, agent_id, scope_id, task_context)

            if not result.compatible:
                rejected.append(capability_id)
                reasons[capability_id] = (
                    f"rejected: failed checks {result.failed_checks}; " + " | ".join(result.reasons)
                )
                continue

            capability = self._capability_registry.get(capability_id)
            relevance = score_capability(capability, task_context)
            reasons[capability_id] = f"selected: relevance={relevance:.3f}; " + " | ".join(result.reasons)
            ranked.append((capability, relevance))

        ranked.sort(key=lambda item: (-item[1], -item[0].created_at.timestamp(), item[0].capability_id))
        selected = [capability.capability_id for capability, _relevance in ranked]

        return CapabilitySelectionResult(
            selected_capabilities=selected, rejected_capabilities=rejected, selection_reasons=reasons,
        )

    @staticmethod
    def _validate_id(value, field_name):
        if not value or not isinstance(value, str):
            raise InvalidCapabilitySelectionError(f"{field_name} is required and must be a non-empty string")
