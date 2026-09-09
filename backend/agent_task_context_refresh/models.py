from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ContextRefreshResult:
    """LLMAgentTaskContextRefreshService.refresh()'s complete account of
    one re-resolution attempt for a task's own relevant_context.

    previous_context_version/new_context_version are both Commit #1's own
    LLMAgentTaskContextSnapshot -- the existing versioning/snapshot
    mechanism this series already built, reused verbatim rather than a
    second one. When nothing actually needed to change (refreshed=False),
    new_context_version is identical to previous_context_version -- no
    redundant snapshot is taken for a no-op refresh (Rule/Test: "fresh
    context is handled without unnecessary replacement").

    added_sources/removed_sources are full relevant_context-shaped dicts
    (added: newly discovered relevant sources not already present;
    removed: confirmed-stale sources dropped from the refreshed
    relevant_context). stale_sources is the plain context_id list of
    every currently-relevant_context entry a freshness check found
    STALE -- a deliberate, tested overlap with removed_sources' own ids
    (every removed source is stale, but stale_sources also exists as its
    own diagnostic field so a caller can see what freshness flagged even
    before deciding whether to act on it), the same "distinct fields
    that may legitimately overlap" precedent this repository's own
    DependencyCheckResult already established elsewhere.

    Only entries confirmed STALE are ever removed -- anything not
    confirmed stale (including every entry when no freshness_service was
    supplied at all) is preserved untouched (Rule: "do not silently
    remove still-valid explicit task context").
    """

    task_id: str
    refreshed: bool
    previous_context_version: object
    new_context_version: object
    added_sources: list
    removed_sources: list
    stale_sources: list
    reason: Optional[str]
