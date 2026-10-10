from dataclasses import dataclass


@dataclass(frozen=True)
class TaskContextDiff:
    """LLMAgentTaskContextDiffService.diff()'s complete, deterministic
    comparison of two persisted Commit #10 TaskContextSnapshot records
    for the same task.

    added/removed/unchanged are lists of {"context_id", "entry",
    "provenance"} dicts -- the same item shape Commit #8's own
    ContextReconciliationResult and Commit #9's own
    ContextConflictResolutionResult already use, so a caller familiar
    with either can read this one the same way. entry is the
    relevant_context-shaped dict from whichever snapshot the id came
    from (to_version for added/unchanged, from_version for removed);
    provenance is the matching backend.llm.context_provenance.
    LLMContextProvenance object (or None), embedded verbatim.

    changed is a list of {"context_id", "from_entry", "to_entry",
    "from_provenance", "to_provenance"} dicts -- a source_id present in
    both snapshots whose content or provenance source_version disagrees;
    both sides are always kept, mirroring Commit #8's own `changed`
    shape exactly.

    provenance_changes is a list of {"context_id", "from_provenance",
    "to_provenance"} dicts -- every common source_id whose provenance
    record itself differs between the two snapshots (source_type,
    source_id, source_version, or excerpt), independent of whether its
    content also changed (Rule: "preserve provenance for changed
    entries" -- surfaced as its own signal, not folded silently into
    `changed`).

    summary is a compact, human-readable rollup: counts for each of the
    five lists above, plus from_version/to_version, so a caller does not
    have to len() five lists just to answer "did anything change".
    """

    task_id: str
    from_version: int
    to_version: int
    added: list
    removed: list
    changed: list
    unchanged: list
    provenance_changes: list
    summary: dict
