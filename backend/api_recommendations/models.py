from dataclasses import dataclass


SCHEMA = "SCHEMA"
ENDPOINT = "ENDPOINT"
PERFORMANCE = "PERFORMANCE"
RELIABILITY = "RELIABILITY"
CATEGORIES = frozenset({SCHEMA, ENDPOINT, PERFORMANCE, RELIABILITY})


@dataclass(frozen=True)
class LLMAPIRecommendation:
    """One suggested API design improvement for a candidate.

    This record is advisory only -- LLMAPIRecommendationService never
    modifies the candidate, its schemas, or the notebook it came from; it
    only ever appends new recommendation records grounded in evidence that
    already exists.
    """

    recommendation_id: str
    candidate_id: str
    category: str
    change: str
    rationale: str
    confidence: float
    severity: str
