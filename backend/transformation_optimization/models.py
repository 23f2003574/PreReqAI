from dataclasses import dataclass

LOW = "LOW"
MEDIUM = "MEDIUM"
HIGH = "HIGH"
LEVELS = frozenset({LOW, MEDIUM, HIGH})


@dataclass(frozen=True)
class LLMOptimizationRecommendation:
    """One LLM-proposed, evidence-grounded performance optimization for an
    already-verified transformation -- inert data, never applied automatically.

    target is the cell_index (as a string) the recommendation concerns, one
    of the execution's own applied_cells. expected_impact is a
    {"magnitude", "description"} dict -- magnitude is LOW/MEDIUM/HIGH and
    description is the required evidence/rationale for the claimed
    improvement, never empty. risk (also LOW/MEDIUM/HIGH) is tracked as its
    own axis so a high-impact recommendation can still be flagged as
    high-risk rather than being conflated with impact.
    """

    recommendation_id: str
    execution_id: str
    target: str
    optimization: str
    expected_impact: dict
    confidence: float
    risk: str
