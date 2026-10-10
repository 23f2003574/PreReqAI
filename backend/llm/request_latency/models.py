import re
from dataclasses import dataclass
from datetime import datetime

# Same secret-redaction convention already used by backend.llm.tool_results,
# backend.llm.tool_execution, backend.transformation_audit, and
# backend.api_recommendation_export. Kept local, as those modules keep their
# own copies, rather than refactoring them here.
_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{10,}"),
    re.compile(r"AKIA[A-Z0-9]{12,}"),
    re.compile(r"(?i)bearer\s+\S+"),
    re.compile(r"(?i)\b(api[_-]?key|token|secret|password)\s*[:=]\s*\S+"),
    re.compile(r"^[A-Fa-f0-9]{32,}$"),
    re.compile(r"^[A-Za-z0-9+/]{40,}={0,2}$"),
)


def _looks_secret(value: str) -> bool:
    return any(pattern.search(value) for pattern in _SECRET_PATTERNS)


class InvalidRequestLatencyError(ValueError):
    """Raised when an LLMRequestLatency fails validation."""


class SecretInRequestLatencyError(InvalidRequestLatencyError):
    """Raised when a field looks like it carries a credential."""


@dataclass(frozen=True)
class LLMRequestLatency:
    """One completed LLM request's lifecycle duration.

    Carries only what backend.llm.audit.LLMRequestAudit already tracks --
    request_id, provider, model, status, and the timestamps it derives
    duration from -- so there is no prompt, response, or message content
    for this record to ever leak; nothing here is copied from an
    LLMRequest/LLMResponse.
    """

    request_id: str
    provider: str
    model: str
    duration: float
    status: str
    recorded_at: datetime

    def validate(self):
        if not self.request_id or not isinstance(self.request_id, str):
            raise InvalidRequestLatencyError("request_id is required")

        if not self.provider or not isinstance(self.provider, str):
            raise InvalidRequestLatencyError("provider is required")

        if not self.model or not isinstance(self.model, str):
            raise InvalidRequestLatencyError("model is required")

        if isinstance(self.duration, bool) or not isinstance(self.duration, (int, float)):
            raise InvalidRequestLatencyError("duration must be a number")
        if self.duration < 0:
            raise InvalidRequestLatencyError("duration must not be negative")

        if not self.status or not isinstance(self.status, str):
            raise InvalidRequestLatencyError("status is required")

        if not isinstance(self.recorded_at, datetime):
            raise InvalidRequestLatencyError("recorded_at must be a datetime")

        if any(_looks_secret(value) for value in (self.provider, self.model, self.status)):
            raise SecretInRequestLatencyError(
                f"request {self.request_id!r} carries a field that looks like a credential"
            )
