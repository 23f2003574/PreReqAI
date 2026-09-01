from dataclasses import dataclass

UNKNOWN_TOOL = "UNKNOWN_TOOL"
DISABLED_TOOL = "DISABLED_TOOL"
INVALID_DEPENDENCY = "INVALID_DEPENDENCY"
DEPENDENCY_CYCLE = "DEPENDENCY_CYCLE"
PERMISSION_CONFLICT = "PERMISSION_CONFLICT"
CATEGORIES = frozenset(
    {UNKNOWN_TOOL, DISABLED_TOOL, INVALID_DEPENDENCY, DEPENDENCY_CYCLE, PERMISSION_CONFLICT}
)


@dataclass(frozen=True)
class LLMAgentPlanFinding:
    """One reason a Commit #1 LLMAgentPlan step cannot proceed to execution.

    step_id names the step the finding concerns. category is one of
    CATEGORIES. blocking is True for every category this service currently
    raises -- there is no advisory finding yet -- but the field exists so a
    later commit can add non-blocking findings without changing this shape.
    Producing a finding never mutates the plan it concerns.
    """

    step_id: str
    category: str
    message: str
    blocking: bool
