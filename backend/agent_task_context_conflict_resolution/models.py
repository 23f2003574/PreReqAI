from dataclasses import dataclass


@dataclass(frozen=True)
class ContextConflictResolutionResult:
    """LLMAgentTaskContextConflictResolver.resolve()'s complete,
    provenance-preserving account of adjudicating one batch of Commit #8
    conflicts for task_id.

    resolved/discarded_sources are lists of {"context_id", "entry",
    "provenance"} dicts -- the same item shape Commit #8's own
    ContextReconciliationResult already uses, so a caller can feed either
    straight back into further processing without reshaping. entry is
    the winning (resolved) or losing (discarded) side's relevant_context-
    shaped dict; provenance is the matching backend.llm.context_provenance.
    LLMContextProvenance object (or None), embedded verbatim -- never
    dropped, even for a discarded source (Rule: "never resolve a conflict
    by silently discarding provenance").

    decisions is a list of {"context_id", "decision", "reason"} dicts,
    one per conflict actually resolved -- decision is one of
    "kept_stored"/"kept_fresh"/"discarded_unauthorized", reason is a
    human-readable, deterministic account of why (Rule: "decisions must
    be deterministic and explainable").

    unresolved_conflicts holds the original conflict dicts, entirely
    unchanged, for anything this resolver could not adjudicate with a
    real signal (no fabricated decision) -- Rule: "unresolvable conflicts
    remain explicit".

    reasons maps every considered context_id (resolved or not) to its own
    explanatory text -- the same "never silently imply a decision"
    discipline this repository's own resolvers already keep.
    """

    task_id: str
    resolved: list
    decisions: list
    discarded_sources: list
    unresolved_conflicts: list
    reasons: dict
