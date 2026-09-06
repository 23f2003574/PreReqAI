import json
from datetime import datetime, timezone

from backend.agent_policy_risk_review_metrics import LLMAgentRiskReviewMetrics
from backend.agent_policy_risk_review_queue import EXPIRED, PENDING

from .models import ReviewReport

# The project's own export convention (backend.agent_policy_reporting,
# itself mirroring backend.llm.security_reports /
# backend.serialization's dataclasses.asdict() -> JSON approach): a small
# closed set of supported formats and an explicit rejection of anything
# else, rather than a new reporting format.
SUPPORTED_FORMATS = frozenset({"json"})

# How many entries reviewer_workload keeps, to stay concise -- ranking,
# not an unbounded dump, the same TOP_N discipline
# backend.agent_policy_reporting.LLMAgentPolicyReportService already uses.
TOP_N = 10


class UnsupportedFormatError(ValueError):
    """Raised when export() is called with a format this project doesn't support."""


class LLMAgentRiskReviewReportService:
    """Turns Commit #11's own ReviewMetrics into a concise, read-only
    ReviewReport for operators -- no new dashboard or observability
    framework, no second aggregation.

    Reuses backend.agent_policy_reporting.LLMAgentPolicyReportService's
    own shape almost exactly (itself mirroring
    backend.llm.security_reports): generate() only re-shapes what
    LLMAgentRiskReviewMetrics.summarize() already returns -- it never
    reads backend.agent_policy_risk_review_queue directly, never calls
    claim()/complete()/enqueue(), and never computes a count Commit #11
    doesn't already expose (see Rules: "Keep reporting separate from
    metric collection"). Commit #11 already refuses a secret-looking
    scope_id before running any query (SecretInScopeError) and every
    count/list it returns is already payload-free by its own rules
    (status/risk_level/outcome/reviewer/timestamps only, never
    action_context or decision.reasons/provenance), so this service
    adds no redaction pass of its own -- there is nothing left to
    redact (see Rules: "Exclude sensitive action payloads").

    export() follows this repository's own JSON convention (sort_keys,
    indent, default=str) rather than a new format: the same report
    always serializes to the same string.
    """

    def __init__(self, metrics_service: LLMAgentRiskReviewMetrics):
        self._metrics_service = metrics_service

    @staticmethod
    def _ranked_workload(reviewer_workload: dict) -> list:
        """reviewer_workload (ReviewMetrics.reviewer_workload), ranked by
        total workload (active + resolved) descending, ties broken by
        reviewer ascending, capped at TOP_N -- deterministic regardless
        of the underlying dict's own iteration order."""
        ranked = sorted(
            reviewer_workload.items(),
            key=lambda entry: (-(entry[1]["active"] + entry[1]["resolved"]), entry[0]),
        )
        return [{"reviewer": reviewer, **counts} for reviewer, counts in ranked[:TOP_N]]

    @staticmethod
    def _sorted_by_created(stuck_items: list, status: str) -> list:
        matching = [dict(entry) for entry in stuck_items if entry["status"] == status]
        return sorted(matching, key=lambda entry: entry["created_at"])

    def generate(self, scope_id: str, filters: dict = None) -> ReviewReport:
        """Build a ReviewReport for scope_id from Commit #11's own
        metrics, narrowed by the same `filters`
        LLMAgentRiskReviewMetrics.summarize() already accepts (start/
        end/status/risk_level/reviewer).

        Deterministic for identical underlying queue data and filters,
        except for generated_at, which is always the real current time.

        Raises:
            ValueError, SecretInScopeError, InvalidMetricsFilterError:
                Propagated unchanged from
                LLMAgentRiskReviewMetrics.summarize()
        """
        metrics = self._metrics_service.summarize(scope_id, filters)

        return ReviewReport(
            scope_id=scope_id,
            generated_at=datetime.now(timezone.utc),
            filters=dict(filters) if filters else {},
            volume={"total": metrics.total, "by_status": dict(metrics.by_status)},
            approval_vs_rejection=dict(metrics.by_outcome),
            risk_level_distribution=dict(metrics.by_risk_level),
            reviewer_workload=self._ranked_workload(metrics.reviewer_workload),
            resolution_time={"average_seconds": metrics.average_resolution_seconds},
            pending_items=self._sorted_by_created(metrics.stuck_items, PENDING),
            expired_items=self._sorted_by_created(metrics.stuck_items, EXPIRED),
            provenance={
                "source": "backend.agent_policy_risk_review_metrics.LLMAgentRiskReviewMetrics",
                "record_count": metrics.total,
            },
        )

    def export(self, report: ReviewReport, format: str = "json") -> str:
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
