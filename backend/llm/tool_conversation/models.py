from dataclasses import dataclass, field
from typing import Any, Optional

# What the model did with its turn.
FINAL_RESPONSE = "FINAL_RESPONSE"
TOOL_CALL = "TOOL_CALL"
BLOCKED = "BLOCKED"
KINDS = frozenset({FINAL_RESPONSE, TOOL_CALL, BLOCKED})

# Context item types, which LLMContextService.build turns into message roles.
ASSISTANT_ROLE = "assistant"

# How many tool calls one conversation may make before the loop is cut off.
DEFAULT_MAX_TOOL_CALLS = 5


class ConversationOrderError(ValueError):
    """Raised when a tool result does not answer the call that is outstanding.

    Tool calls and their results must stay paired and in order; feeding back
    a result for a different call, or for no call at all, would corrupt the
    transcript the next turn is built from.
    """


@dataclass(frozen=True)
class LLMToolConversationRequest:
    """What a caller needs to run one tool-calling conversation.

    A request value object in the same spirit as the existing
    LLMRouteRequest -- it describes the conversation, it does not hold its
    transcript. The transcript lives where every other LLM call's context
    lives: in LLMContextService under context_id, which the caller creates
    and seeds with the system prompt and opening user message before the
    first next_action().

    Attributes:
        request_id: Identifies this conversation. Each turn derives its own
            orchestration request id from it, so per-turn records stay
            distinct
        context_id: The LLMContextService context holding the transcript
        subject: Who the conversation acts for, passed to Commit #4
            authorization -- a string, or a collection of scope identifiers
        route_request: The Commit #3 LLMRouteRequest used for every turn
        budget_scope_id: When set, the Commit #8 budget scope each turn is
            checked against by the orchestration pipeline
        estimated_tokens: Per-turn estimate handed to that budget check
        max_tool_calls: The ceiling on tool calls in this conversation
    """

    request_id: str
    context_id: str
    subject: Any
    route_request: Any = None
    budget_scope_id: Optional[str] = None
    estimated_tokens: int = 0
    estimated_cost: float = 0.0
    max_tool_calls: int = DEFAULT_MAX_TOOL_CALLS
    temperature: float = 0.0

    def __post_init__(self):
        for name in ("request_id", "context_id"):
            value = getattr(self, name)
            if not value or not isinstance(value, str):
                raise ValueError(f"LLMToolConversationRequest.{name} is required")

        if not isinstance(self.max_tool_calls, int) or isinstance(self.max_tool_calls, bool):
            raise ValueError("max_tool_calls must be an integer")

        if self.max_tool_calls < 0:
            raise ValueError("max_tool_calls must not be negative")


@dataclass(frozen=True)
class LLMToolConversationAction:
    """What the conversation decided to do next.

    Exactly one of the three kinds:

        FINAL_RESPONSE  the model answered; content carries the text
        TOOL_CALL       the model asked for a tool, and that request has
                        already been validated (Commit #2/#3) and authorized
                        (Commit #4); plan carries the READY plan to run
        BLOCKED         nothing may proceed -- budget, permissions, a bad
                        tool call, or the tool-call limit; reason says which

    A TOOL_CALL action is a proposal, not an execution. This service never
    runs a tool: the caller executes the plan with Commit #5 and feeds the
    Commit #6 result back through continue_(), so no tool ever runs without
    the caller deciding to run it.
    """

    request_id: str
    kind: str
    content: Optional[str] = None
    plan: Any = None
    reason: str = ""
    decision: Any = None
    tool_calls_made: int = 0
    errors: list = field(default_factory=list)
