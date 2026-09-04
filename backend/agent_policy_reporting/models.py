from dataclasses import asdict, dataclass
from datetime import datetime


@dataclass(frozen=True)
class PolicyReport:
    """A concise, read-only report built entirely from Commit #8's own
    PolicyMetrics -- never a second aggregation, never a new analytics
    model. Every field here is a direct re-shaping of data
    LLMAgentPolicyMetricsService.summarize() already computed; see
    LLMAgentPolicyReportService.generate() for exactly which.

    Attributes:
        scope_id: The scope this report covers
        generated_at: When this report was produced -- the one field
            that is naturally wall-clock and so is not itself part of
            generate()'s own determinism guarantee (see Commit #9's own
            "deterministic output" rule: the same underlying audit data
            and filters always produce the same report *content*)
        filters: The exact Commit #8 filters this report was generated
            with, echoed back for traceability
        decision_summary: total/allowed/denied/denial_rate, straight from
            PolicyMetrics
        trends: PolicyMetrics.by_period, reshaped into a list sorted by
            period ascending -- the same day-by-day allow/deny breakdown,
            ordered for a trend line rather than left as an unordered
            mapping
        top_policies: PolicyMetrics.by_policy, ranked by total decisions
            descending (ties broken by policy_id) and capped at a
            concise top N
        top_rules: The same ranking, over PolicyMetrics.by_rule
        exception_usage: exception_assisted count and rate, straight from
            PolicyMetrics
        notable_changes: Periods (from trends) whose own denial_rate
            deviates from the overall decision_summary denial_rate by at
            least NOTABLE_DEVIATION_THRESHOLD -- surfaced, not hidden,
            using only data trends already carries; never a second
            enforcement-change detector
        provenance: Which service/store this report's data came from, and
            how many audit records it was built from
    """

    scope_id: str
    generated_at: datetime
    filters: dict
    decision_summary: dict
    trends: list
    top_policies: list
    top_rules: list
    exception_usage: dict
    notable_changes: list
    provenance: dict

    def to_dict(self) -> dict:
        data = asdict(self)
        data["generated_at"] = self.generated_at.isoformat()
        return data
