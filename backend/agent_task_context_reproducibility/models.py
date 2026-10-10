from dataclasses import dataclass

# status vocabulary -- plain strings, the same convention every closed
# status field in this repository already uses (e.g. backend.llm.
# tool_execution's SUCCEEDED/FAILED) rather than a new Enum type.
REPRODUCIBLE = "reproducible"
NON_REPRODUCIBLE = "non_reproducible"
BLOCKED = "blocked"
STATUSES = frozenset({REPRODUCIBLE, NON_REPRODUCIBLE, BLOCKED})


@dataclass(frozen=True)
class TaskContextReproducibilityResult:
    """LLMAgentTaskContextReproducibilityService.assess()'s complete,
    deterministic verdict on whether snapshot_id can still be exactly
    reconstructed for task_id.

    expected_context is Commit #10's own snapshot.resolved_context
    ["context"] -- the ground truth of what was actually persisted.
    replayed_context is Commit #11's own TaskContextReplayResult.context --
    what replaying that same snapshot actually reconstructs. Under
    healthy conditions the two are identical; differences records any
    place they diverge (Rule: "reproducibility means reconstructing the
    same persisted context, not merely producing a semantically similar
    one").

    blockers holds hard reasons the reconstruction cannot be trusted at
    all -- Commit #11's own (Commit #5-derived) integrity findings
    (malformed shape, secret-shaped content, missing/malformed
    provenance) plus this service's own direct source-availability
    findings, both reused/computed verbatim, never re-derived from
    scratch. status is "blocked" whenever blockers is non-empty
    (regardless of differences); "non_reproducible" when blockers is
    empty but differences is not; "reproducible" only when both are
    empty. reproducible is True iff status == "reproducible".

    provenance_complete/source_versions_available/integrity_valid are
    each their own explicit boolean, mirroring the "never silently imply
    a decision" discipline every other *Result in this repository
    already keeps -- a caller can check any one of them directly without
    having to infer it from blockers' own free text.
    """

    status: str
    task_id: str
    snapshot_id: str
    reproducible: bool
    replayed_context: list
    expected_context: list
    differences: list
    provenance_complete: bool
    source_versions_available: bool
    integrity_valid: bool
    blockers: list
