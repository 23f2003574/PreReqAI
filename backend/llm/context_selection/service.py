import json

from ..context import estimate_text_tokens
from ..context_retrieval import score_context


class MixedScopeError(ValueError):
    """Raised when select() is given contexts from more than one scope_id.

    A single selection feeds a single LLM call about one project/notebook/
    API; conflating scopes here would be the kind of silent cross-scope leak
    Commit #1-#3 already refuse.
    """


def content_text(context) -> str:
    """A context's content rendered as one string, the project's JSON convention."""
    content = context.content
    return content if isinstance(content, str) else json.dumps(content, sort_keys=True, default=str)


def content_tokens(context) -> int:
    """Token estimate for a context's content, using the project's own estimator.

    Module-level and reused as-is by Commit #5's LLMContextCompactionService,
    so a context's size is judged identically whether it is being fit into a
    selection or compacted afterward.
    """
    return estimate_text_tokens(content_text(context))


class LLMContextSelectionService:
    """Selects the most useful subset of already-retrieved context for one task.

    Reuses Commit #3's score_context() for relevance -- no second relevance
    system -- and backend.llm.context's estimate_text_tokens() for sizing --
    no second token-management system. Operates purely on the contexts it is
    given: it never reads from or writes to a store, and never mutates the
    LLMProjectContext objects it selects among.
    """

    def score(self, context, task: str) -> float:
        return score_context(context, task).score

    def select(self, contexts: list, task: str, token_budget: int) -> list:
        if not isinstance(task, str):
            raise ValueError("task must be a string")

        if not isinstance(token_budget, int) or isinstance(token_budget, bool) or token_budget <= 0:
            raise ValueError("token_budget must be a positive integer")

        if not contexts:
            return []

        scope_ids = {context.scope_id for context in contexts}
        if len(scope_ids) > 1:
            raise MixedScopeError(
                f"select() was given contexts from more than one scope: {sorted(scope_ids)}"
            )

        candidates = self._prefer_newest_versions(contexts)

        ranked = sorted(
            candidates,
            key=lambda context: (
                -self.score(context, task),
                -context.updated_at.timestamp(),
                context.context_id,
            ),
        )

        selected = []
        used_tokens = 0
        for context in ranked:
            item_tokens = content_tokens(context)
            if used_tokens + item_tokens > token_budget:
                continue
            selected.append(context)
            used_tokens += item_tokens

        return selected

    @staticmethod
    def _prefer_newest_versions(contexts: list) -> list:
        """Deduplicate by context_id, keeping only the most recently updated copy.

        Lets a caller pass overlapping retrievals (e.g. results gathered
        across time) without stale duplicates competing for budget alongside
        their own newer selves.
        """
        newest_by_id = {}
        for context in contexts:
            current = newest_by_id.get(context.context_id)
            if current is None or context.updated_at > current.updated_at:
                newest_by_id[context.context_id] = context
        return list(newest_by_id.values())
