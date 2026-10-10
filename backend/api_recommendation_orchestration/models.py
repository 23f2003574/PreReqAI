from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class LLMAPIRecommendationDecision:
    """The single, deterministic verdict for a notebook's API recommendation
    pipeline -- intent through exposure, schema review, and the risk /
    security / compatibility gates -- replaced (never appended) each time
    recommend() is called for this notebook_id.

    recommendations is the list of Commit #4 recommendation_ids this
    decision covers. blocking_findings/warnings are {"source", "endpoint",
    "category", "message"} dicts drawn from Commit #8 (risk), Commit #10
    (security), and Commit #11 (compatibility) findings -- approved is True
    only when blocking_findings is empty. Producing this decision never
    modifies notebook source or the compiler; it only ever reads what the
    earlier stages already computed.
    """

    decision_id: str
    notebook_id: str
    recommendations: list
    approved: bool
    blocking_findings: list
    warnings: list
    created_at: datetime
