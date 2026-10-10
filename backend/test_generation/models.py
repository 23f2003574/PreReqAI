from dataclasses import dataclass


VALID = "VALID"
INVALID = "INVALID"
EDGE = "EDGE"
CATEGORIES = frozenset({VALID, INVALID, EDGE})


@dataclass(frozen=True)
class LLMGeneratedTest:
    """One generated test case for an API candidate.

    input/expected_output are always grounded in the candidate's Commit #4/#5
    schemas -- for VALID/EDGE tests both are schema-conformant field->value
    maps; for INVALID tests, expected_output is the structured marker
    {"raises": True, "reason": "..."} instead, since an invalid payload is
    never meant to produce a real output (see Commit #6). This record is
    inert data -- generating it never runs the candidate function.
    """

    test_id: str
    candidate_id: str
    scenario: str
    input: dict
    expected_output: dict
    category: str
    confidence: float
