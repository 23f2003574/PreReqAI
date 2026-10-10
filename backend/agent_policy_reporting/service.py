import json
from datetime import datetime, timezone

from backend.agent_policy_metrics import LLMAgentPolicyMetricsService

from .models import PolicyReport

# The project's own export convention (backend.llm.security_reports,
# itself built on backend.llm.observability_reports /
# backend.serialization's dataclasses.asdict() -> JSON approach): a small
# closed set of supported formats and an explicit rejection of anything
# else, rather than a new reporting format.
SUPPORTED_FORMATS = frozenset({"json"})

# How far a period's own denial_rate must deviate from the report's
# overall denial_rate (in absolute percentage points, 0.0-1.0) before it
# is surfaced as a "notable enforcement change" -- a fixed, documented
# threshold rather than a caller-tunable one, so the same underlying data
# always produces the same set of notable periods.
NOTABLE_DEVIATION_THRESHOLD = 0.25

# How many entries top_policies/top_rules keep, to stay "concise" per
# this commit's own goal -- ranking, not an unbounded dump.
TOP_N = 10


class UnsupportedFormatError(ValueError):
    """Raised when export() is called with a format this project doesn't support."""


class LLMAgentPolicyReportService:
    """Turns Commit #8's own PolicyMetrics into a concise, read-only
    PolicyReport for operators and debugging -- no new analytics
    infrastructure, no second aggregation.

    Reuses backend.llm.security_reports.LLMSecurityReportService's own
    shape almost exactly: generate() only re-shapes what
    LLMAgentPolicyMetricsService.summarize() already returns (decision
    counts, by_policy, by_rule, by_period) into report-facing fields --
    it never reads backend.agent_policy_audit directly, never calls
    LLMAgentPolicyEvaluator/LLMAgentPolicyResolver/
    LLMAgentPolicyDecisionEngine/LLMAgentPolicyEnforcement, and never
    computes a count Commit #8 doesn't already expose (see Rules: "Keep
    report generation separate from metric collection"). Commit #8
    already refuses a secret-looking scope_id before running any query
    (SecretInScopeError) and every count it returns is already
    payload-free by Commit #7's own audit rules, so this service adds no
    redaction pass of its own -- there is nothing left to redact.

    notable_changes is the one field that is not a Commit #8 aggregate
    verbatim: it flags which periods in PolicyMetrics.by_period deviate
    from the report's own overall denial_rate by at least
    NOTABLE_DEVIATION_THRESHOLD -- computed purely from data Commit #8
    already returned, never a second data source or a stored history of
    prior reports.

    export() follows this repository's own JSON convention (sort_keys,
    indent, default=str for datetimes) rather than a new format: the same
    report always serializes to the same string.
    """

    def __init__(self, metrics_service: LLMAgentPolicyMetricsService):
        self._metrics_service = metrics_service

    @staticmethod
    def _ranked(buckets: dict) -> list:
        """buckets (PolicyMetrics.by_policy or .by_rule), ranked by total
        descending, ties broken by identifier ascending, capped at
        TOP_N -- deterministic regardless of the underlying dict's own
        iteration order."""
        ranked = sorted(buckets.items(), key=lambda item: (-item[1]["total"], item[0]))
        return [
            {"id": identifier, **counts}
            for identifier, counts in ranked[:TOP_N]
        ]

    @staticmethod
    def _trends(by_period: dict) -> list:
        """PolicyMetrics.by_period, ordered by period ascending, each
        entry carrying its own denial_rate alongside the raw counts."""
        trends = []
        for period in sorted(by_period):
            counts = by_period[period]
            total = counts["total"]
            trends.append(
                {
                    "period": period,
                    "total": total,
                    "allowed": counts["allowed"],
                    "denied": counts["denied"],
                    "denial_rate": (counts["denied"] / total) if total else 0.0,
                }
            )
        return trends

    @staticmethod
    def _notable_changes(trends: list, overall_denial_rate: float) -> list:
        notable = []
        for entry in trends:
            deviation = entry["denial_rate"] - overall_denial_rate
            if abs(deviation) >= NOTABLE_DEVIATION_THRESHOLD:
                notable.append(
                    {
                        "period": entry["period"],
                        "denial_rate": entry["denial_rate"],
                        "deviation_from_overall": deviation,
                    }
                )
        return notable

    def generate(self, scope_id: str, filters: dict = None) -> PolicyReport:
        """Build a PolicyReport for scope_id from Commit #8's own metrics,
        narrowed by the same `filters` LLMAgentPolicyMetricsService.summarize()
        already accepts (start/end/decision/policy_id/rule_id).

        Deterministic for identical underlying audit data and filters,
        except for generated_at, which is always the real current time.

        Raises:
            ValueError, SecretInScopeError, InvalidMetricsFilterError:
                Propagated unchanged from
                LLMAgentPolicyMetricsService.summarize()
        """
        metrics = self._metrics_service.summarize(scope_id, filters)

        decision_summary = {
            "total": metrics.total,
            "allowed": metrics.allowed,
            "denied": metrics.denied,
            "denial_rate": metrics.denial_rate,
        }
        trends = self._trends(metrics.by_period)
        exception_usage = {
            "exception_assisted": metrics.exception_assisted,
            "exception_rate": (metrics.exception_assisted / metrics.total) if metrics.total else 0.0,
        }

        return PolicyReport(
            scope_id=scope_id,
            generated_at=datetime.now(timezone.utc),
            filters=dict(filters) if filters else {},
            decision_summary=decision_summary,
            trends=trends,
            top_policies=self._ranked(metrics.by_policy),
            top_rules=self._ranked(metrics.by_rule),
            exception_usage=exception_usage,
            notable_changes=self._notable_changes(trends, metrics.denial_rate),
            provenance={
                "source": "backend.agent_policy_audit.LLMAgentPolicyAuditService",
                "record_count": metrics.total,
            },
        )

    def export(self, report: PolicyReport, format: str = "json") -> str:
        """Serialize report; the same report always serializes to the
        same string.

        Raises:
            UnsupportedFormatError: If format is not one of SUPPORTED_FORMATS
        """
        if format not in SUPPORTED_FORMATS:
            raise UnsupportedFormatError(
                f"format {format!r} is not supported; must be one of {sorted(SUPPORTED_FORMATS)}"
            )

        return json.dumps(report.to_dict(), sort_keys=True, indent=2, default=str)
