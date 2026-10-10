import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from ..usage_anomalies import SEVERITIES

# Same secret-redaction convention already used by backend.llm.tool_results,
# backend.llm.request_latency, backend.llm.request_errors, and others. Kept
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


OPEN = "OPEN"
RESOLVED = "RESOLVED"
STATUSES = frozenset({OPEN, RESOLVED})


class InvalidUsageAnomalyAlertError(ValueError):
    """Raised when an LLMUsageAnomalyAlert fails validation."""


class SecretInAlertMessageError(InvalidUsageAnomalyAlertError):
    """Raised when an alert's message looks like it carries a credential."""


@dataclass(frozen=True)
class LLMUsageAnomalyAlert:
    """A structured, human-actionable alert for one Commit #7 confirmed anomaly.

    message is built only from the anomaly's own metric name, scope, and
    numeric observed/baseline/deviation values -- never anything from a
    prompt, response, or provider payload -- so there is nothing here for a
    secret to ride in on; validate() still rejects one on the rare chance
    the scope string itself looks like a credential.
    """

    alert_id: str
    anomaly_id: str
    severity: str
    status: str
    message: str
    created_at: datetime
    resolved_at: Optional[datetime]

    def validate(self):
        if not self.alert_id or not isinstance(self.alert_id, str):
            raise InvalidUsageAnomalyAlertError("alert_id is required")

        if not self.anomaly_id or not isinstance(self.anomaly_id, str):
            raise InvalidUsageAnomalyAlertError("anomaly_id is required")

        if self.severity not in SEVERITIES:
            raise InvalidUsageAnomalyAlertError(f"severity must be one of {sorted(SEVERITIES)}")

        if self.status not in STATUSES:
            raise InvalidUsageAnomalyAlertError(f"status must be one of {sorted(STATUSES)}")

        if not self.message or not isinstance(self.message, str):
            raise InvalidUsageAnomalyAlertError("message is required")

        if not isinstance(self.created_at, datetime):
            raise InvalidUsageAnomalyAlertError("created_at must be a datetime")

        if self.status == RESOLVED and self.resolved_at is None:
            raise InvalidUsageAnomalyAlertError("a RESOLVED alert must carry resolved_at")
        if self.status == OPEN and self.resolved_at is not None:
            raise InvalidUsageAnomalyAlertError("an OPEN alert must not carry resolved_at")
        if self.resolved_at is not None and not isinstance(self.resolved_at, datetime):
            raise InvalidUsageAnomalyAlertError("resolved_at must be a datetime or None")

        if _looks_secret(self.message):
            raise SecretInAlertMessageError(
                f"alert {self.alert_id!r} message looks like it carries a credential"
            )
