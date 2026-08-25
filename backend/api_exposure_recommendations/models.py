from dataclasses import dataclass


@dataclass(frozen=True)
class LLMAPIExposureRecommendation:
    """One concrete, reviewable recommendation for exposing an existing
    notebook function as an API endpoint, grounded in a Commit #3 intent.

    function_name is always one of the notebook's own extracted functions
    (backend.notebook_analysis) and one Commit #3 already confidently
    mapped to a real function -- an intent operation Commit #3 itself
    flagged ambiguous (function=None) never produces a recommendation
    here; it is skipped, not guessed. method is one of the compiler's own
    supported HTTP methods (backend.compilation_plan.ENDPOINT_METHODS).
    Producing this record never modifies notebook source, the compiler,
    or any generated API code.
    """

    recommendation_id: str
    function_name: str
    endpoint_name: str
    method: str
    rationale: str
    confidence: float
