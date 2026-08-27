from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

# The context item type (and therefore the message role, since
# LLMContextService.build emits {"role": item.type, ...}) a normalized tool
# result carries into an LLM request.
TOOL_ROLE = "tool"

# Default ceiling for how much rendered output may enter LLM context,
# measured with this project's own estimate (backend.llm.context.
# estimate_text_tokens) against the same kind of token budget
# LLMContext.token_budget already uses.
DEFAULT_OUTPUT_TOKEN_BUDGET = 2000


class InvalidToolResultError(ValueError):
    """Raised when a result is not fit to enter LLM context."""


@dataclass(frozen=True)
class LLMToolResult:
    """One Commit #5 execution record, normalized for an LLM to read.

    status is the execution's own status, unchanged -- this is a
    presentation of an existing record, not a second protocol layered over
    it, so SUCCEEDED/FAILED/DENIED/REJECTED keep exactly the meaning
    backend.llm.tool_execution gave them.

    output holds the successful tool's return value converted to
    JSON-safe form, with every string leaf passed through the codebase's
    secret-redaction check; it is None for every status but SUCCEEDED.
    error is a short redacted explanation, None only when SUCCEEDED.
    metadata records what a reader needs to judge the output without
    re-running anything: the tool and plan it came from, the token estimate,
    and whether it had to be trimmed to fit the budget.
    """

    execution_id: str
    status: str
    output: Any
    error: Optional[str]
    metadata: dict = field(default_factory=dict)
    completed_at: Optional[datetime] = None
