from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional


@dataclass(frozen=True)
class LLMToolCallDecision:
    """The single, deterministic outcome of orchestrating one tool call.

    Shaped after the codebase's existing orchestration decisions --
    LLMRequestDecision (one per LLM request) and LLMCodePatchDecision (one
    per patch, keyed by execution_id) -- and it exists for the same reason
    they do: a pipeline with this many gates needs one record that says
    what finally happened, rather than leaving a caller to reassemble it
    from six services.

    status is the execution's own status vocabulary, unchanged, so
    SUCCEEDED / FAILED / DENIED / REJECTED / TIMED_OUT / CANCELLED keep
    exactly the meaning backend.llm.tool_execution gave them. allowed is
    True only for SUCCEEDED -- it answers "did the tool actually run and
    return", not "was the subject permitted".

    plan_id is None only when the call was too malformed to plan.
    execution_id is None whenever a gate refused before any execution
    existed -- a validation or permission rejection -- exactly as
    LLMCodePatchDecision uses it. result carries the Commit #6 normalized
    LLMToolResult, the form that is safe to hand back to the model.

    The subject is deliberately not stored here: the Commit #8 audit trail
    already records who the call was for, redacted, and one place for that
    fact is better than two.
    """

    decision_id: str
    request_id: Optional[str]
    plan_id: Optional[str]
    execution_id: Optional[str]
    tool_name: Optional[str]
    status: str
    allowed: bool
    reason: str
    attempts: int = 0
    duration: Optional[float] = None
    result: Any = None
    created_at: Optional[datetime] = None
