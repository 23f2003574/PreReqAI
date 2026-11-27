import pytest

from backend.parsing import stated_prerequisites as sp

pytestmark = pytest.mark.prereqai


@pytest.mark.parametrize("sentence", [
    "Prior knowledge of reinforcement learning is helpful but not required.",
    "This paper requires no knowledge of linear algebra.",
    "We do not assume any background in probability.",
    "Familiarity with calculus is not needed to follow this paper.",
    "Readers do not need to be familiar with linear algebra.",
    "We don't assume familiarity with optimization.",
    "The method can be used without any prior knowledge of statistics.",
    "Knowledge of information theory is helpful but we explain what is needed.",
])
def test_negated_or_optional_statements_state_no_prerequisite(sentence):
    hit = sp.find_in_sentence(sentence)
    assert hit == {"cue": None, "subjects": [], "concepts": []}


@pytest.mark.parametrize("sentence,expected", [
    ("We assume familiarity with linear algebra and probability theory.", {"Linear Algebra", "Probability"}),
    ("Readers should be comfortable with calculus.", {"Calculus"}),
    ("Readers should be able to follow derivations that use linear algebra.", {"Linear Algebra"}),
    ("Basic knowledge of Markov decision processes is needed to follow Section 3.", {"Markov Decision Process"}),
])
def test_positive_statements_are_still_found(sentence, expected):
    hit = sp.find_in_sentence(sentence)
    assert hit["cue"] == "explicit" and set(hit["subjects"] + hit["concepts"]) == expected


def test_negated_statements_never_raise_a_grade():
    assert sp.evaluate([{"sentence": "Prior knowledge of reinforcement learning is helpful but not required.", "expected": []}])["fp"] == 0
