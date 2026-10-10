import json
from datetime import datetime, timezone

from ..security_metrics import LLMSecurityMetricsService
from ..security_policy import BLOCK

# The project's own export convention (backend.llm.observability_reports,
# itself built on backend.api_recommendation_export /
# backend.serialization's dataclasses.asdict() -> JSON approach): a small
# closed set of supported formats and an explicit rejection of anything
# else, rather than a new reporting format.
SUPPORTED_FORMATS = frozenset({"json"})

_REQUIRED_FIELDS = (
    "scope",
    "period",
    "generated_at",
    "decision_counts",
    "policy_counts",
    "finding_counts",
    "input_output_breakdown",
    "blocking_events",
)


class UnsupportedFormatError(ValueError):
    """Raised when export() is called with a format this project doesn't support."""


class MalformedReportError(ValueError):
    """Raised when validate() is given a payload that isn't a well-formed report."""


class LLMSecurityReportService:
    """Exports Commit #9's security metrics as a stable, serializable report.

    generate() only re-shapes what LLMSecurityMetricsService already
    returns -- summary() for decision_counts/finding_counts, by_policy()
    for policy_counts, by_direction() for input_output_breakdown -- no
    new aggregation, no data Commit #9 doesn't already expose. Commit #9
    already refuses a secret-looking scope before running any query
    (SecretInScopeError), so a report can never be generated for one, and
    every count it returns is already payload-free by Commit #6's own
    audit rules; this service adds no redaction pass of its own because
    there is nothing left to redact.

    blocking_events is the one field that is not itself an existing
    Commit #9 aggregate: it lists every BLOCK-decision audit record for
    scope/period (via Commit #9's own records(scope, period), the same
    scope-safety and period validation every other metric already goes
    through), each reduced to reference fields only -- audit_id,
    request_id, direction, policy_ids, finding_types, created_at -- never
    a prompt, a response, or anything resembling one, since
    LLMSecurityAudit never carried those to begin with (see Rules:
    "Include blocking events with references, not sensitive payloads").
    Events are sorted by (created_at, audit_id) so the same underlying
    audit state always serializes to the same order, regardless of the
    audit store's own iteration order.

    export() follows this repository's own JSON convention (sort_keys,
    indent, default=str for datetimes) rather than a new format: the same
    report dict always serializes to the same string.
    """

    def __init__(self, metrics_service: LLMSecurityMetricsService):
        self._metrics_service = metrics_service

    @staticmethod
    def _event_for(audit) -> dict:
        return {
            "audit_id": audit.audit_id,
            "request_id": audit.request_id,
            "direction": audit.direction,
            "policy_ids": sorted(audit.policy_ids),
            "finding_types": sorted(audit.finding_types),
            "created_at": audit.created_at.isoformat(),
        }

    def _blocking_events(self, scope, period) -> list:
        blocked = [audit for audit in self._metrics_service.records(scope, period) if audit.decision == BLOCK]
        blocked.sort(key=lambda audit: (audit.created_at.isoformat(), audit.audit_id))
        return [self._event_for(audit) for audit in blocked]

    def generate(self, scope, period) -> dict:
        """A JSON-safe report dict for scope over period, built only from
        Commit #9's own metrics and audit records.
        """
        start, end = period
        decision_summary = self._metrics_service.summary(scope, period)

        return {
            "scope": scope,
            "period": {"start": start.isoformat(), "end": end.isoformat()},
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "decision_counts": {
                "allowed": decision_summary["allowed"],
                "redacted": decision_summary["redacted"],
                "blocked": decision_summary["blocked"],
            },
            "policy_counts": self._metrics_service.by_policy(scope, period),
            "finding_counts": decision_summary["findings"],
            "input_output_breakdown": self._metrics_service.by_direction(scope, period),
            "blocking_events": self._blocking_events(scope, period),
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

        if not isinstance(report["blocking_events"], list):
            raise MalformedReportError("report['blocking_events'] must be a list")

        return True
