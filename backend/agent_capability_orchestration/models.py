from dataclasses import dataclass


@dataclass(frozen=True)
class CapabilityPreparationResult:
    """prepare()'s complete, structured account of what is available and
    usable for one (agent_id, scope_id, task_context) request, from
    resolution through selection.

    resolved_capabilities is Commit #2's own list of available
    capability_ids (archived/policy-excluded ones already gone).
    selected_capabilities is Commit #6's own best-first subset of those,
    ready to hand to execute_selected(). compatibility and
    dependency_status are {capability_id: <real Commit #5
    CapabilityCompatibilityResult / Commit #4 DependencyCheckResult>}
    for every resolved capability -- the actual, unmodified objects
    those commits' own services produced, embedded verbatim rather than
    re-summarized (the same convention this repository's other
    orchestrators already keep for their own sub-results). rejections
    maps every resolved-but-not-selected capability_id to a
    human-readable account of why, the same dict-of-reasons idiom
    Commit #2's resolution_reasons and Commit #6's selection_reasons
    already establish.

    A pure record of the orchestrator's own coordination: it performs
    no resolution, checking, or selection of its own.
    """

    resolved_capabilities: list
    selected_capabilities: list
    compatibility: dict
    dependency_status: dict
    rejections: dict
