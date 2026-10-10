from dataclasses import dataclass

NONE = "NONE"
RETRYABLE = "RETRYABLE"
PERMANENT = "PERMANENT"
PERMISSION_DENIED = "PERMISSION_DENIED"
DEPENDENCY_FAILURE = "DEPENDENCY_FAILURE"
CATEGORIES = frozenset({NONE, RETRYABLE, PERMANENT, PERMISSION_DENIED, DEPENDENCY_FAILURE})

RETRY = "RETRY"
CONTINUE = "CONTINUE"
BLOCK = "BLOCK"
FAIL = "FAIL"
ACTIONS = frozenset({RETRY, CONTINUE, BLOCK, FAIL})


@dataclass(frozen=True)
class LLMAgentFailureClassification:
    """Why one step of a plan execution is, or is not, currently failing.

    step_id is the step this classification concerns -- never blurred
    across steps, so a caller always knows exactly which step and why.
    category is one of CATEGORIES; reason is a short, human-readable
    explanation carrying the step's own recorded error or status
    verbatim, never a re-derived or summarized one.
    """

    step_id: str
    category: str
    reason: str
