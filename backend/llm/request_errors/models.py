import re
from dataclasses import dataclass
from datetime import datetime

# Same secret-redaction convention already used by backend.llm.tool_results,
# backend.llm.tool_execution, backend.llm.request_latency, and others. Kept
# local, as those modules keep their own copies, rather than refactoring
# them here.
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


UNKNOWN = "UNKNOWN"


class InvalidRequestErrorMetricError(ValueError):
    """Raised when an LLMRequestErrorMetric fails validation."""


class SecretInRequestErrorMetricError(InvalidRequestErrorMetricError):
    """Raised when a field looks like it carries a credential."""


@dataclass(frozen=True)
class LLMRequestErrorMetric:
    """One classified failure from an actual LLM request attempt.

    error_type is always one of backend.llm.request_errors.service's
    curated KNOWN_ERRORS labels, or UNKNOWN for anything else -- never a
    raw exception message, which is also why there is no field here for
    one: an exception's str() can carry request content or a credential,
    so it is never stored, only the exception's classified type.
    """

    request_id: str
    provider: str
    model: str
    error_type: str
    retryable: bool
    recorded_at: datetime

    def validate(self):
        if not self.request_id or not isinstance(self.request_id, str):
            raise InvalidRequestErrorMetricError("request_id is required")

        if not self.provider or not isinstance(self.provider, str):
            raise InvalidRequestErrorMetricError("provider is required")

        if not self.model or not isinstance(self.model, str):
            raise InvalidRequestErrorMetricError("model is required")

        if not self.error_type or not isinstance(self.error_type, str):
            raise InvalidRequestErrorMetricError("error_type is required")

        if not isinstance(self.retryable, bool):
            raise InvalidRequestErrorMetricError("retryable must be a bool")

        if not isinstance(self.recorded_at, datetime):
            raise InvalidRequestErrorMetricError("recorded_at must be a datetime")

        if any(_looks_secret(value) for value in (self.provider, self.model, self.error_type)):
            raise SecretInRequestErrorMetricError(
                f"request {self.request_id!r} carries a field that looks like a credential"
            )
