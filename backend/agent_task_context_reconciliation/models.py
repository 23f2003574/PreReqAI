from dataclasses import dataclass


@dataclass(frozen=True)
class ContextReconciliationResult:
    """LLMAgentTaskContextReconciler.reconcile()'s complete, read-only
    comparison of task_id's stored relevant_context against a fresh
    Commit #2 resolution.

    added/removed/unchanged are lists of {"context_id", "entry",
    "provenance"} dicts -- entry is the relevant_context-shaped dict
    (from the fresh resolution for added, from the stored task context
    for removed/unchanged), provenance is the matching backend.llm.
    context_provenance.LLMContextProvenance object (or None), embedded
    verbatim -- the existing repository type, never reshaped (Rule:
    "preserve source/version provenance in every difference").

    added is genuinely new sources Commit #2's resolver discovered that
    are not already stored. removed/changed/unchanged are computed by
    independently re-checking every *stored* entry's current authorization
    and live content -- never by looking for it in the fresh resolution's
    own selected_context, which (by that resolver's own design) always
    carries every already-stored entry through unconditionally and so
    could never reveal that one has gone stale, been denied, or drifted.

    changed is a list of {"context_id", "stored_entry", "fresh_entry",
    "stored_provenance", "fresh_provenance"} dicts -- a stored entry whose
    live project-context content now differs from what was stored; both
    sides are kept so a caller can see exactly what would change, never
    just the newer value winning silently.

    stale is a plain list of context_id strings freshness confirmed
    stale among the *stored* relevant_context (only populated when a
    freshness_service was supplied) -- diagnostic, like Commit #5/#7's
    own stale_sources.

    conflicts holds an entry whose current authorization check explicitly
    denies it (Rule: "surface conflicts instead of silently choosing
    between competing sources" / Test: "scope/authorization violations
    are surfaced") -- always also present in removed (removed answers
    "is it gone", conflicts answers "was its absence a rule violation"),
    the same deliberate, tested field overlap this series already
    established for stale_sources/removed_sources in Commit #7.
    """

    task_id: str
    agent_id: str
    scope_id: str
    added: list
    removed: list
    changed: list
    unchanged: list
    stale: list
    conflicts: list
