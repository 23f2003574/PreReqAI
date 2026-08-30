import dataclasses
import json
from datetime import datetime, timezone

from ..observability_dashboard import LLMObservabilityDashboardService

# The project's own export convention (backend.api_recommendation_export,
# itself built on backend.serialization's dataclasses.asdict() -> JSON
# approach): a small closed set of supported formats and an explicit
# rejection of anything else, rather than a new reporting format.
SUPPORTED_FORMATS = frozenset({"json"})

_REQUIRED_FIELDS = (
    "scope",
    "period",
    "generated_at",
    "usage",
    "cost",
    "latency",
    "error_rate",
    "provider_reliability",
    "anomalies",
)


class UnsupportedFormatError(ValueError):
    """Raised when export() is called with a format this project doesn't support."""


class MalformedReportError(ValueError):
    """Raised when validate() is given a payload that isn't a well-formed report."""


class LLMObservabilityReportService:
    """Exports Commit #9's dashboard summary as a stable, serializable report.

    generate() only re-shapes what LLMObservabilityDashboardService.summary()
    already returns -- no new analytics, no data the dashboard doesn't
    already expose. Commit #9 already refuses a secret-looking scope before
    running any query, so a report can never be generated for one; nothing
    else in a report is free-text, so there is no separate redaction pass
    to invent here. export() follows this repository's own JSON convention
    (sort_keys, indent, default=str for datetimes) rather than a new format.
    """

    def __init__(self, dashboard_service: LLMObservabilityDashboardService):
        self._dashboard_service = dashboard_service

    @staticmethod
    def _anomaly_to_dict(anomaly) -> dict:
        payload = dataclasses.asdict(anomaly)
        payload["detected_at"] = anomaly.detected_at.isoformat()
        return payload

    def generate(self, scope, period) -> dict:
        """A JSON-safe report dict for scope over period; reuses Commit #9 verbatim."""
        start, end = period
        summary = self._dashboard_service.summary(scope, period)

        return {
            "scope": scope,
            "period": {"start": start.isoformat(), "end": end.isoformat()},
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "usage": summary["usage"],
            "cost": summary["cost"],
            "latency": summary["latency"],
            "error_rate": summary["error_rate"],
            "provider_reliability": summary["provider_reliability"],
            "anomalies": [self._anomaly_to_dict(anomaly) for anomaly in summary["anomalies"]],
        }

    def export(self, report: dict, format: str) -> str:
        """Serialize report; the same report always serializes to the same string."""
        if format not in SUPPORTED_FORMATS:
            raise UnsupportedFormatError(
                f"format {format!r} is not supported; must be one of {sorted(SUPPORTED_FORMATS)}"
            )

        return json.dumps(report, sort_keys=True, indent=2, default=str)

    def validate(self, report: dict) -> bool:
        """Structural well-formedness of a report dict -- never re-derives its values."""
        if not isinstance(report, dict):
            raise MalformedReportError("report must be a dict")

        missing = [field for field in _REQUIRED_FIELDS if field not in report]
        if missing:
            raise MalformedReportError(f"report is missing required field(s): {missing}")

        period = report["period"]
        if not isinstance(period, dict) or "start" not in period or "end" not in period:
            raise MalformedReportError("report['period'] must include 'start' and 'end'")

        if not isinstance(report["anomalies"], list):
            raise MalformedReportError("report['anomalies'] must be a list")

        return True
