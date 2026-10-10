from dataclasses import dataclass
from datetime import datetime
from typing import Optional

TOKENS = "TOKENS"
COST = "COST"
LATENCY = "LATENCY"
ERROR_RATE = "ERROR_RATE"
METRICS = frozenset({TOKENS, COST, LATENCY, ERROR_RATE})

UNKNOWN = "UNKNOWN"
NORMAL = "NORMAL"
MODERATE = "MODERATE"
CRITICAL = "CRITICAL"
SEVERITIES = frozenset({UNKNOWN, NORMAL, MODERATE, CRITICAL})


class InvalidUsageAnomalyError(ValueError):
    """Raised when an LLMUsageAnomaly fails validation."""


@dataclass(frozen=True)
class LLMUsageAnomaly:
    """One metric's deviation from its own recent history for one scope.

    baseline/deviation are None exactly when severity is UNKNOWN -- there
    was not enough prior history to judge observed against, so nothing is
    fabricated and UNKNOWN is never treated as anomalous. Otherwise
    deviation is the relative change of observed over baseline; severity
    only escalates for an increase (a spike), never for a drop.
    """

    anomaly_id: str
    scope: Optional[str]
    metric: str
    observed: float
    baseline: Optional[float]
    deviation: Optional[float]
    severity: str
    detected_at: datetime

    def validate(self):
        if not self.anomaly_id or not isinstance(self.anomaly_id, str):
            raise InvalidUsageAnomalyError("anomaly_id is required")

        if self.scope is not None and not isinstance(self.scope, str):
            raise InvalidUsageAnomalyError("scope must be a string or None")

        if self.metric not in METRICS:
            raise InvalidUsageAnomalyError(f"metric must be one of {sorted(METRICS)}")

        if isinstance(self.observed, bool) or not isinstance(self.observed, (int, float)):
            raise InvalidUsageAnomalyError("observed must be a number")

        if self.severity not in SEVERITIES:
            raise InvalidUsageAnomalyError(f"severity must be one of {sorted(SEVERITIES)}")

        if self.severity == UNKNOWN:
            if self.baseline is not None or self.deviation is not None:
                raise InvalidUsageAnomalyError(
                    "an UNKNOWN-severity anomaly must carry no baseline/deviation"
                )
        else:
            if self.baseline is None or self.deviation is None:
                raise InvalidUsageAnomalyError(
                    f"a {self.severity} anomaly must carry both baseline and deviation"
                )

        if not isinstance(self.detected_at, datetime):
            raise InvalidUsageAnomalyError("detected_at must be a datetime")
