from dataclasses import dataclass
from datetime import datetime
from typing import Optional

SUCCEEDED = "SUCCEEDED"
FAILED = "FAILED"
RUN_STATUSES = frozenset({SUCCEEDED, FAILED})


@dataclass(frozen=True)
class LLMEvaluationRun:
    """One execution of a Commit #1 case through the existing LLM orchestration.

    Reuses backend.llm.orchestration.LLMRequestOrchestrationService end to
    end -- this record only captures what that pipeline decided and
    returned, it invents no execution path of its own. provider/model are
    whatever the orchestration's LLMRequestDecision recorded, including for
    a FAILED run where a provider was attempted and raised. output is the
    raw model content, secret-redacted the same way backend.llm.tool_results
    redacts tool output, and is always None for a FAILED run -- there is
    nothing succeeded output to capture, only the request_id and
    provider/model attempted are preserved so the failure stays traceable.
    """

    run_id: str
    case_id: str
    request_id: str
    provider: Optional[str]
    model: Optional[str]
    output: Optional[str]
    status: str
    started_at: datetime
    completed_at: datetime
