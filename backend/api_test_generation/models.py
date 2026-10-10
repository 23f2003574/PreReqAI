from dataclasses import dataclass


@dataclass(frozen=True)
class LLMAPITestCase:
    """One reviewable API test case for a Commit #4 recommendation's
    endpoint, generated from the notebook's own schema-grounded test data.

    request/expected_response are never independently generated here --
    they are read straight from backend.test_generation's own
    LLMGeneratedTest (input/expected_output), from the original
    notebook-to-API series, already validated against the candidate's real
    input/output schemas (its own VALID/INVALID/EDGE category rules
    included), so this test case can never drift from what the compiler
    actually generates. Like the underlying service, these are inert
    records -- this service never executes the API or the candidate
    function.
    """

    test_id: str
    endpoint: str
    scenario: str
    request: dict
    expected_response: dict
    category: str
    confidence: float
