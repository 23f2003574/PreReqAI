from dataclasses import dataclass, field


@dataclass(frozen=True)
class ReviewMetrics(object):
    """LLMAgentRiskReviewMetrics.summarize()'s complete, read-only
    aggregate snapshot of one scope's Commit #8 review queue.

    Every count here is derived purely from Commit #8 ReviewItem fields
    that are already labels/identifiers/timestamps -- status,
    decision.risk_level, resolution["outcome"], claimed_by/resolved_by,
    created_at/resolved_at -- never from action_context or
    decision.reasons/provenance, so this snapshot can never carry a
    reviewed action's own arguments or payload (see Rules: "Do not
    expose sensitive action payloads").

    Attributes:
        scope_id: The scope this snapshot summarizes
        total: Every item matching the query, regardless of status
        by_status: PENDING/CLAIMED/RESOLVED/EXPIRED counts -- Commit
            #8's own closed status vocabulary, always fully populated
            (zero-valued for a status with no matching items)
        by_outcome: APPROVED/REJECTED counts, counted only across
            RESOLVED items -- always fully populated
        by_risk_level: Commit #1's own closed LEVEL_LOW/MEDIUM/HIGH/
            CRITICAL vocabulary, always fully populated
        average_resolution_seconds: The mean (resolved_at - created_at)
            across RESOLVED items matching the query, in seconds; 0.0
            when there are none (see Rules: "Handle empty datasets" --
            never an error, never None pretending to be a real average)
        reviewer_workload: {reviewer: {"active": count of items this
            reviewer currently CLAIMED, "resolved": count of items this
            reviewer has RESOLVED}} -- open-ended, since reviewer
            identifiers can't be pre-enumerated (mirrors
            backend.agent_policy_metrics.PolicyMetrics's own by_policy/
            by_rule sparsity convention); a reviewer with zero of either
            never appears
        stuck_items: Every matching PENDING or EXPIRED item (the ones
            with no forward progress), each as {item_id, scope_id,
            status, risk_level, created_at, expires_at} -- identifiers
            and timestamps only, added for Commit #12's own report to
            reshape for "identifying review bottlenecks" without that
            report needing a second source of truth or its own copy of
            this iteration (see Rules: "Keep reporting separate from
            metric collection")
    """

    scope_id: str
    total: int
    by_status: dict
    by_outcome: dict
    by_risk_level: dict
    average_resolution_seconds: float
    reviewer_workload: dict = field(default_factory=dict)
    stuck_items: list = field(default_factory=list)
