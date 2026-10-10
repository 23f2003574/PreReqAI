from datetime import datetime

from backend.agent_task_context_resolution import ResolvedAgentTaskContext
from backend.llm.context_compaction import LLMContextCompactionService
from backend.llm.project_context import LLMProjectContext

from .models import BudgetedAgentTaskContext


class InvalidTaskContextBudgetError(ValueError):
    """Raised when budget() is given something other than a
    ResolvedAgentTaskContext, malformed limits, or a selected_context
    entry that cannot be tracked through budgeting (not a dict, or
    missing its own context_id)."""


class LLMAgentTaskContextBudgeter:
    """Deterministically fits one resolved task context's selected_context
    under a token budget.

    Not a second compaction or token-counting engine: every byte of
    fitting logic is backend.llm.context_compaction.
    LLMContextCompactionService.compact() itself, unchanged -- already-
    under-budget input returned as deep copies unchanged, oversized
    entries shrunk to a preview before being dropped, and token sizing
    entirely content_tokens()/estimate_text_tokens() (Commit #4/#1 of the
    original context-injection series). This class adds only the
    Commit #2-specific plumbing compact() has no notion of: converting
    Commit #2's own plain-dict selected_context entries into the
    LLMProjectContext objects compact() operates on, and translating
    Rule "preserve mandatory task inputs and constraints" into terms
    compact() already understands.

    "Mandatory" is read at its most literal for backend.agent_task_context.
    LLMAgentTaskContext.inputs/.constraints themselves: budget() never
    reads or reshapes either field, so their survival on the returned
    task_context is structural, not enforced by any code path here.  For
    *context entries*, "mandatory" means the task's own explicit
    relevant_context (Commit #2's own resolver always places these first
    in selected_context, unconditionally) -- each such entry is tagged
    metadata["priority"]="high" (compact()'s own existing, pre-established
    priority signal -- see backend.llm.context_compaction.
    LLMContextCompactionService.compact()'s own preserve() docstring)
    before compaction, so it is allocated space first and compacted only
    once every other protected entry already has been. This does not
    make mandatory entries literally undroppable: if the mandatory pool
    alone exceeds the whole budget, compact()'s own existing behavior
    still shrinks/drops the excess -- "never exceed the requested
    budget" is the harder constraint, exactly the precedence
    compact() already encodes; nothing here overrides it.

    budget() only ever reads the ResolvedAgentTaskContext it is given and
    the LLMProjectContext objects it constructs locally from it -- no
    task context, project context, or memory store is ever touched, so
    there is nothing here that could mutate stored state.
    """

    def __init__(self, context_compaction: LLMContextCompactionService = None):
        self._context_compaction = context_compaction or LLMContextCompactionService()

    def budget(self, context: ResolvedAgentTaskContext, limits) -> BudgetedAgentTaskContext:
        """Fit context.selected_context under limits' token budget.

        Raises:
            InvalidTaskContextBudgetError: If context is not a
                ResolvedAgentTaskContext, limits does not resolve to a
                positive integer token budget, or a selected_context
                entry is not a dict or carries no context_id
        """
        if not isinstance(context, ResolvedAgentTaskContext):
            raise InvalidTaskContextBudgetError(
                f"context must be a ResolvedAgentTaskContext, got {type(context).__name__}"
            )
        token_budget = self._resolve_token_budget(limits)

        explicit_ids = {
            entry.get("context_id")
            for entry in context.task_context.relevant_context
            if entry.get("context_id")
        }

        candidates = [
            self._to_project_context(entry, context.scope_id, explicit_ids) for entry in context.selected_context
        ]

        compacted = self._context_compaction.compact(candidates, token_budget)
        compacted_by_id = {entry.context_id: entry for entry in compacted}

        selected_context = []
        dropped_context = []
        reasons = {}
        truncation_applied = False

        for candidate in candidates:
            result = compacted_by_id.get(candidate.context_id)
            if result is None:
                dropped_context.append(candidate.to_dict())
                reasons[candidate.context_id] = (
                    f"context {candidate.context_id!r} dropped: did not fit budget {token_budget}"
                )
                truncation_applied = True
                continue

            selected_context.append(result.to_dict())
            if result.metadata.get("compacted"):
                reasons[candidate.context_id] = (
                    f"context {candidate.context_id!r} shrunk to fit budget {token_budget}"
                )
                truncation_applied = True
            else:
                reasons[candidate.context_id] = f"context {candidate.context_id!r} kept unchanged"

        estimated_tokens = self._context_compaction.estimate(compacted)

        return BudgetedAgentTaskContext(
            task_id=context.task_id,
            agent_id=context.agent_id,
            scope_id=context.scope_id,
            task_context=context.task_context,
            selected_context=selected_context,
            dropped_context=dropped_context,
            estimated_tokens=estimated_tokens,
            budget=token_budget,
            truncation_applied=truncation_applied,
            reasons=reasons,
            provenance=list(context.provenance),
            selected_memories=list(context.selected_memories),
        )

    @staticmethod
    def _to_project_context(entry, scope_id: str, explicit_ids: set) -> LLMProjectContext:
        if not isinstance(entry, dict):
            raise InvalidTaskContextBudgetError(
                f"each selected_context entry must be a dict, got {type(entry).__name__}"
            )

        context_id = entry.get("context_id")
        if not context_id or not isinstance(context_id, str):
            raise InvalidTaskContextBudgetError(
                "each selected_context entry must carry its own non-empty context_id to be budgeted"
            )

        metadata = dict(entry.get("metadata") or {})
        if context_id in explicit_ids:
            metadata.setdefault("priority", "high")

        kwargs = dict(
            scope_id=entry.get("scope_id") or scope_id,
            context_type=entry.get("context_type") or "fact",
            content=entry.get("content"),
            context_id=context_id,
            metadata=metadata,
        )
        for field_name in ("created_at", "updated_at"):
            value = entry.get(field_name)
            if isinstance(value, str):
                kwargs[field_name] = datetime.fromisoformat(value)
            elif isinstance(value, datetime):
                kwargs[field_name] = value

        return LLMProjectContext(**kwargs)

    @staticmethod
    def _resolve_token_budget(limits) -> int:
        if isinstance(limits, dict):
            token_budget = limits.get("token_budget")
            if token_budget is None:
                raise InvalidTaskContextBudgetError("limits dict must include a 'token_budget' key")
        elif isinstance(limits, int) and not isinstance(limits, bool):
            token_budget = limits
        else:
            raise InvalidTaskContextBudgetError(
                "limits must be a positive integer or a dict with a 'token_budget' key"
            )

        if not isinstance(token_budget, int) or isinstance(token_budget, bool) or token_budget <= 0:
            raise InvalidTaskContextBudgetError("token_budget must be a positive integer")
        return token_budget
