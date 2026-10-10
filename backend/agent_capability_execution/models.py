from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

# Same RUNNING/SUCCEEDED/FAILED strings backend.llm.tool_execution already
# uses for its own execution statuses -- redeclared locally rather than
# imported, since that module's own STATUSES also includes DENIED/
# REJECTED/TIMED_OUT/CANCELLED, none of which apply to this service's own
# simpler start -> complete/fail lifecycle (Rule: "start -> complete/fail
# is the valid lifecycle"). Same redeclare-a-subset-of-an-existing-
# vocabulary precedent backend.llm.tool_validation's REQUIRED/TYPE/...
# already set for backend.input_validation's own rule vocabulary.
RUNNING = "RUNNING"
SUCCEEDED = "SUCCEEDED"
FAILED = "FAILED"
STATUSES = frozenset({RUNNING, SUCCEEDED, FAILED})
TERMINAL_STATUSES = frozenset({SUCCEEDED, FAILED})


@dataclass(frozen=True)
class LLMAgentCapabilityExecution:
    """One immutable snapshot of a single attempt to use a Commit #1
    capability -- this module's own single source of truth for that
    attempt's current lifecycle state, never a second execution engine
    and never itself an execution: nothing here calls, schedules, or
    otherwise runs the capability it describes (Rule: "this records
    execution; it does not execute capabilities").

    Frozen, the same immutability backend.llm.tool_execution.
    LLMToolExecution already keeps for its own execution records in this
    exact domain family: a status transition (start -> complete/fail)
    never mutates a stored instance in place, it replaces it with a new
    one via dataclasses.replace() (LLMAgentCapabilityExecutionService's
    own job), the same replace-on-transition discipline
    backend.llm.tools.LLMToolRegistryService._set_enabled() and
    backend.llm.tool_audit.LLMToolAuditService.record_authorization()
    already use for their own immutable records.

    capability_version is the exact Commit #1 LLMAgentCapability.version
    in effect when start() was called, captured verbatim and never
    re-derived later -- so a record always says exactly which version of
    a capability was actually attempted, even if that capability's own
    current version has since moved on (Rule: "execution records must
    identify the exact capability version used").

    input_reference/output_reference are never the raw input/output
    payload itself -- see LLMAgentCapabilityExecutionService's own
    _reference_for(), which redacts through the repository's canonical
    backend.llm.secret_redaction.LLMSecretRedactionService and then
    stores only a content hash, never the payload (Rule: "do not persist
    secrets or sensitive payloads directly"). error is a short,
    redacted, human-readable string (never hashed away, since a caller
    still needs to read it) -- the same "result/error, never a raw
    traceback" discipline LLMToolExecution's own docstring already
    states, for the same reason: a traceback carries local variables,
    exactly where credentials tend to sit.
    """

    execution_id: str = field(default_factory=lambda: str(uuid4()))
    agent_id: str = ""
    capability_id: str = ""
    capability_version: str = ""
    scope_id: str = ""
    status: str = RUNNING
    input_reference: Optional[str] = None
    output_reference: Optional[str] = None
    error: Optional[str] = None
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        data = asdict(self)
        data["started_at"] = self.started_at.isoformat()
        data["completed_at"] = None if self.completed_at is None else self.completed_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "LLMAgentCapabilityExecution":
        payload = dict(data)
        value = payload.get("started_at")
        if isinstance(value, str):
            payload["started_at"] = datetime.fromisoformat(value)
        value = payload.get("completed_at")
        if isinstance(value, str):
            payload["completed_at"] = datetime.fromisoformat(value)
        return cls(**payload)
