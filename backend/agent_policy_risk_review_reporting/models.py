from dataclasses import asdict, dataclass
from datetime import datetime


@dataclass(frozen=True)
class ReviewReport(object):
    """A concise, read-only report built entirely from Commit #11's own
    ReviewMetrics -- never a second aggregation, never a new analytics
    model. Every field here is a direct re-shaping of data
    LLMAgentRiskReviewMetrics.summarize() already computed; see
    LLMAgentRiskReviewReportService.generate() for exactly which.

    Mirrors backend.agent_policy_reporting.PolicyReport's own shape
    (itself mirroring backend.llm.security_reports) almost exactly, one
    series over: a report is a metrics snapshot reshaped for an
    operator, nothing more.

    Attributes:
        scope_id: The scope this report covers
        generated_at: When this report was produced -- the one field
            that is naturally wall-clock and so is not itself part of
            generate()'s own determinism guarantee (the same underlying
            queue data and filters always produce the same report
            *content*, per Rules: "Deterministic")
        filters: The exact Commit #11 filters this report was generated
            with, echoed back for traceability
        volume: total/by_status, straight from ReviewMetrics
        approval_vs_rejection: by_outcome, straight from ReviewMetrics
        risk_level_distribution: by_risk_level, straight from
            ReviewMetrics
        reviewer_workload: ReviewMetrics.reviewer_workload, ranked by
            total workload (active + resolved) descending, ties broken
            by reviewer ascending, and capped at TOP_N -- the same
            ranking-for-conciseness reshaping PolicyReport's own
            top_policies/top_rules already apply
        resolution_time: {"average_seconds": ...}, straight from
            ReviewMetrics.average_resolution_seconds
        pending_items: ReviewMetrics.stuck_items narrowed to PENDING,
            oldest first -- identifiers and timestamps only, for
            "identifying review bottlenecks" (see Rules: "Exclude
            sensitive action payloads")
        expired_items: The same, narrowed to EXPIRED
        provenance: Which service this report's data came from, and how
            many review items it was built from
    """

    scope_id: str
    generated_at: datetime
    filters: dict
    volume: dict
    approval_vs_rejection: dict
    risk_level_distribution: dict
    reviewer_workload: list
    resolution_time: dict
    pending_items: list
    expired_items: list
    provenance: dict

    def to_dict(self) -> dict:
        data = asdict(self)
        data["generated_at"] = self.generated_at.isoformat()
        for key in ("pending_items", "expired_items"):
            data[key] = [
                {
                    **entry,
                    "created_at": entry["created_at"].isoformat() if entry.get("created_at") else None,
                    "expires_at": entry["expires_at"].isoformat() if entry.get("expires_at") else None,
                }
                for entry in data[key]
            ]
        return data
