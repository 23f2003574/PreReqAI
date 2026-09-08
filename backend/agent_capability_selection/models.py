from dataclasses import dataclass


@dataclass(frozen=True)
class CapabilitySelectionResult:
    """LLMAgentCapabilitySelector.select()'s complete, structured outcome
    for one (agent_id, scope_id, task_context, candidates) request.

    selected_capabilities and rejected_capabilities are capability_id
    strings, best-ranked first in selected_capabilities -- never full
    LLMAgentCapability records, since a candidate named in an explicit
    candidates list may not even be registered (Commit #1's own
    LLMAgentCapabilityRegistry.get(capability_id) can always retrieve
    the full record for one that is).
    selection_reasons maps every considered capability_id (selected or
    rejected) to a human-readable account of why, the same
    "never silently imply a decision" discipline
    backend.agent_capability_resolution.ResolvedAgentCapabilities.
    resolution_reasons already established for this series' own Commit
    #2.

    A pure record of the selector's own decision: it performs no
    selection of its own.
    """

    selected_capabilities: list
    rejected_capabilities: list
    selection_reasons: dict
