from dataclasses import dataclass

# Compact, categorical names for which check failed -- distinct from
# `reasons`' own full human-readable narrative, so a caller can filter on
# "which checks failed" without parsing message text.
CHECK_EXISTENCE = "capability_registered"
CHECK_AVAILABILITY = "capability_available"
CHECK_CONTRACT = "contract_present"
CHECK_REQUIRED_CONTEXT = "required_context_satisfied"
CHECK_DEPENDENCIES = "dependencies_satisfied"


@dataclass(frozen=True)
class CapabilityCompatibilityResult:
    """LLMAgentCapabilityCompatibility.check()'s complete, structured
    outcome for one (capability_id, agent_id, scope_id, context) request.

    failed_checks names every CHECK_* that did not pass (empty means
    compatible is True). warnings are advisory, non-blocking notices
    that never affect `compatible` on their own. reasons is the full,
    ordered narrative of every check performed, whether it passed or
    failed -- the same "never silently imply a decision" discipline
    every other *Result/*Decision in this repository already keeps, so a
    caller can see exactly why compatible ended up True or False without
    re-running any of the underlying checks itself.
    """

    capability_id: str
    agent_id: str
    scope_id: str
    compatible: bool
    failed_checks: list
    warnings: list
    reasons: list
