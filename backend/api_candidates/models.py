from dataclasses import dataclass


@dataclass
class LLMAPICandidate:
    """A notebook function the LLM judges suitable for exposure as an API.

    function_name is copied verbatim from the Commit #1 analysis it was
    validated against -- LLMAPICandidateService never renames or rewrites
    the function it identifies, it only describes it.
    """

    candidate_id: str
    notebook_id: str
    function_name: str
    inputs: list
    outputs: list
    confidence: float
    rationale: str
