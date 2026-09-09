from dataclasses import dataclass


@dataclass(frozen=True)
class ContextIntegrityResult:
    """LLMAgentTaskContextIntegrityService.validate()'s complete,
    never-silently-repairing account of one AgentContextPackage's fitness
    to reach an agent request.

    valid is True iff errors is empty -- warnings never affect it, the
    same "advisory vs blocking" split every other *Result in this
    repository already keeps (e.g. backend.agent_capability_compatibility.
    CapabilityCompatibilityResult.warnings).

    invalid_sources/stale_sources/provenance_issues each hold only
    context_id/memory_id values (or, for provenance_issues, a small
    {"id", "issue"} dict) drawn from package.context/package.memories --
    never from package.task, which is checked separately and reported
    only through errors/warnings (Rule: "keep mandatory task data
    distinguishable from supplemental context" -- kept distinguishable
    structurally, by never mixing a task-level issue into a
    source-specific bucket). A source id may legitimately appear in more
    than one bucket (e.g. both unauthorized and provenance-broken); each
    bucket answers a different question and none of them are mutually
    exclusive.
    """

    valid: bool
    errors: list
    warnings: list
    invalid_sources: list
    stale_sources: list
    provenance_issues: list
