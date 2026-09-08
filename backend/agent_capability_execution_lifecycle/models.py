from dataclasses import dataclass
from typing import Any, Optional

# This orchestrator's own outcome vocabulary -- richer than Commit #7's
# bare RUNNING/SUCCEEDED/FAILED (which describes one durable execution
# record's own lifecycle), because Rule "validation/policy failures must
# be distinguishable from capability execution failures" needs to say
# *where* an attempt stopped, including three ways it can be rejected
# before an execution record is even created at all. Redeclared locally
# rather than mixing imports from Commit #7's own module, the same
# "redeclare a related-but-not-identical vocabulary locally" precedent
# Commit #7 itself already set against backend.llm.tool_execution.
REJECTED_UNKNOWN_CAPABILITY = "REJECTED_UNKNOWN_CAPABILITY"
REJECTED_INVALID_INPUT = "REJECTED_INVALID_INPUT"
REJECTED_POLICY_DENIED = "REJECTED_POLICY_DENIED"
REJECTED_INVALID_OUTPUT = "REJECTED_INVALID_OUTPUT"
FAILED = "FAILED"
SUCCEEDED = "SUCCEEDED"
STATUSES = frozenset(
    {
        REJECTED_UNKNOWN_CAPABILITY,
        REJECTED_INVALID_INPUT,
        REJECTED_POLICY_DENIED,
        REJECTED_INVALID_OUTPUT,
        FAILED,
        SUCCEEDED,
    }
)

# Statuses reached before any Commit #7 execution record is ever created
# -- Rule "any failed precondition must prevent execution" means none of
# these ever have an execution_id.
PRECONDITION_STATUSES = frozenset({REJECTED_UNKNOWN_CAPABILITY, REJECTED_INVALID_INPUT, REJECTED_POLICY_DENIED})


@dataclass(frozen=True)
class CapabilityExecutionResult:
    """LLMAgentCapabilityExecutionService.execute()'s complete outcome
    for one (agent_id, capability_id, scope_id, input_payload, context)
    attempt.

    execution_id is None for every PRECONDITION_STATUSES outcome (no
    Commit #7 record was ever created) and set otherwise. output is the
    capability's own real return value on SUCCEEDED, and None for every
    other status -- never a Commit #7-style reference hash, since this
    is the live, synchronous answer handed straight back to the caller
    that just produced/awaited it, not the durable record (Commit #7's
    own execution_service.get(execution_id) is where the redacted
    input_reference/output_reference/capability_version live; this
    Result deliberately does not duplicate capability_version onto
    itself -- it is reachable, exactly preserved, through execution_id).

    validation is Commit #8's own ExecutionValidationResult -- from
    validate_start() for every pre-execution outcome, or from
    validate_result() once execution has actually happened; None only
    for REJECTED_UNKNOWN_CAPABILITY and REJECTED_POLICY_DENIED, where no
    contract validation was ever attempted. policy_decision is Commit
    #9's own CapabilityExecutionPolicyResult; None only for
    REJECTED_UNKNOWN_CAPABILITY and REJECTED_INVALID_INPUT, where policy
    was never evaluated (Rule: "any failed precondition must prevent
    execution" -- checks stop at the first failed precondition rather
    than running every later one anyway). error is a short,
    human-readable account of what happened, always present except on
    SUCCEEDED.
    """

    execution_id: Optional[str]
    status: str
    output: Any
    validation: Optional[object]
    policy_decision: Optional[object]
    error: Optional[str]
