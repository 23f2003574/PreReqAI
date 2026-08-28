import json
import re

from ..project_context import LLMProjectContextService
from .models import LLMContextMatch

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list:
    return _TOKEN_PATTERN.findall(text.lower())


def searchable_text(value) -> str:
    """Render content/metadata as one flat string to tokenize.

    Uses the project's JSON rendering convention (json.dumps(sort_keys=True,
    default=str), as backend.llm.tool_results does) so structured content
    and plain strings are both searchable without a second serialization
    format.
    """
    return json.dumps(value, sort_keys=True, default=str)


def score_context(context, query: str) -> LLMContextMatch:
    """Score one context's relevance to a query.

    Module-level and reused as-is by Commit #4's LLMContextSelectionService,
    so relevance is judged identically whether context is being ranked for
    retrieval or scored for selection.
    """
    query_tokens = tokenize(query)
    if not query_tokens:
        return LLMContextMatch(context=context, score=0.0, reason="no query terms")

    haystack = set(tokenize(searchable_text(context.content))) | set(
        tokenize(searchable_text(context.metadata))
    )
    matched = sorted(token for token in set(query_tokens) if token in haystack)
    score = len(matched) / len(set(query_tokens))
    reason = f"matched terms={matched}" if matched else "no matching terms"
    return LLMContextMatch(context=context, score=round(score, 6), reason=reason)


class LLMContextRetrievalService:
    """Ranks and retrieves Commit #1 project context relevant to a query.

    No embeddings or vector search: relevance is a deterministic keyword
    overlap between the query and a context's content/metadata -- the same
    kind of case-insensitive substring matching
    backend.session.ContextRetriever already uses -- broken by recency then
    context_id so results are stable across calls. Scope isolation and
    persistence are entirely delegated to Commit #1's
    LLMProjectContextService.list(); this service holds no state of its own.
    """

    def __init__(self, context_service: LLMProjectContextService):
        self.context_service = context_service

    def rank(self, scope_id: str, query: str) -> list:
        """Every context in scope_id, ranked best-first, in a deterministic order."""
        if not isinstance(query, str):
            raise ValueError("query must be a string")

        contexts = self.context_service.list(scope_id)

        matches = [score_context(context, query) for context in contexts]
        matches.sort(
            key=lambda match: (
                -match.score,
                -match.context.updated_at.timestamp(),
                match.context.context_id,
            )
        )
        return matches

    def retrieve(self, scope_id: str, query: str, limit: int) -> list:
        """The `limit` best-matching contexts in scope_id, best first."""
        if not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0:
            raise ValueError("limit must be a positive integer")

        matches = self.rank(scope_id, query)
        return [match.context for match in matches[:limit]]
