from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class AgentTaskStateValidationResult:
    """LLMAgentTaskStateValidator.validate()'s complete, structured
    outcome for one Commit #1 AgentTask.

    current_state is the task's own current_state exactly as given
    (even when it turns out to be invalid -- Rule: "never silently
    coerce invalid states"); target_state is always None here, since
    validate() checks one task's own consistency, not a move between
    two states (see TransitionValidationResult for that). errors are
    blocking; warnings are advisory only and never affect `valid` --
    the same failed-checks/warnings split
    backend.agent_capability_execution_validation.ExecutionValidationResult
    and backend.agent_capability_compatibility.CapabilityCompatibilityResult
    already keep elsewhere in this repository. valid is exactly `not
    errors`.

    Deterministic and side-effect free: computing a result never
    mutates, persists, or transitions the task it inspects.
    """

    valid: bool
    current_state: Optional[str]
    target_state: Optional[str] = None
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


@dataclass(frozen=True)
class TransitionValidationResult:
    """LLMAgentTaskStateValidator.validate_transition()'s complete,
    structured outcome for one (current_state, target_state) pair.

    current_state/target_state are always the exact values given, even
    when unknown (Rule: "never silently coerce invalid states"). errors
    are blocking; warnings are advisory only (e.g. a legal but no-op
    self-transition) and never affect `valid`. valid is exactly `not
    errors`.
    """

    valid: bool
    current_state: str
    target_state: str
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
