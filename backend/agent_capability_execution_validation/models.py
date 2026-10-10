from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutionValidationResult:
    """LLMAgentCapabilityExecutionValidator.validate_start()/
    validate_result()'s complete, structured outcome for one payload/
    context check against one exact capability version's contract.

    errors are blocking: schema violations (Commit #3's own
    LLMAgentCapabilityContractViolation.message, reused verbatim, never
    re-derived) and unmet required_context/requirements, plus an
    "unknown capability/contract" message when the exact version being
    validated against cannot be resolved at all. warnings are advisory
    only (e.g. a possible secret detected in the payload) and never
    affect `valid` on their own -- the same failed_checks/warnings split
    backend.agent_capability_compatibility.CapabilityCompatibilityResult
    already keeps for an unrelated check in this same series.

    valid is exactly `not errors`.
    """

    valid: bool
    errors: list
    warnings: list
