from dataclasses import dataclass

READY = "READY"
REJECTED = "REJECTED"
STATUSES = frozenset({READY, REJECTED})

# Rule strings for the two rejection reasons the Commit #2 validation service
# raises rather than returns (an unusable tool is a caller bug there, but here
# it is just another reason a plan is REJECTED). They extend that service's
# vocabulary without modifying it -- the error entries themselves are its own
# LLMToolValidationError.
UNKNOWN_TOOL = "unknown_tool"
DISABLED_TOOL = "disabled_tool"
MALFORMED_SCHEMA = "malformed_schema"


@dataclass(frozen=True)
class LLMToolInvocationPlan:
    """A validated, reviewable proposal to call one registered tool.

    tool_call is the original LLM-produced tool call, preserved verbatim and
    never rewritten -- arguments is the same payload, copied out for
    convenience, so a reviewer can always compare what was planned against
    what the model actually asked for. status is READY only when the tool is
    registered, enabled, well-defined, and every argument passed Commit #2's
    schema validation; anything else is REJECTED, with errors carrying the
    structured LLMToolValidationError entries that say why (empty when
    READY).

    A plan is never executed. It is only ever a proposal -- running it
    belongs to a later commit.
    """

    plan_id: str
    tool_name: str
    arguments: dict
    rationale: str
    status: str
    tool_call: dict
    errors: list
