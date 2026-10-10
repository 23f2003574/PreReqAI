from dataclasses import dataclass


@dataclass(frozen=True)
class TaskContextReplayResult:
    """LLMAgentTaskContextReplayService.replay()'s complete account of
    reconstructing one historical TaskContextSnapshot.

    context/provenance are Commit #10's own snapshot.resolved_context
    ["context"]/snapshot.provenance, read back verbatim -- never
    re-resolved, re-ranked, or filled in from whatever the task's
    current relevant_context or the project context store say *now*
    (Rule: "never silently substitute current context for missing
    historical data"). context_version is that same snapshot's own.

    reproducible is True iff differences is empty -- the same "advisory
    fields never silently imply success" split every other *Result in
    this repository already keeps. differences is a flat list of
    human-readable strings covering both structural problems within the
    snapshot record itself (e.g. a missing resolved_context payload) and
    whatever backend.agent_task_context_integrity.
    LLMAgentTaskContextIntegrityService.validate() itself found wrong
    with the reconstructed context (missing/inconsistent provenance,
    malformed message shape, secret-shaped content) -- reused verbatim,
    not re-derived.
    """

    snapshot_id: str
    task_id: str
    context_version: int
    context: list
    provenance: list
    reproducible: bool
    differences: list
