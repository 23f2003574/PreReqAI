import pytest

from backend.parsing import stated_prerequisites as sp

pytestmark = pytest.mark.prereqai

# (sentence, subjects a reader finds stated); written for this test, not taken from the benchmark papers
CASES = [
    ("We assume familiarity with statistics.", ["Statistics"]),
    ("We assume familiarity with linear algebra, calculus and probability.", ["Linear Algebra", "Calculus", "Probability"]),
    ("Readers should know probability and optimization.", ["Probability", "Optimization"]),
    ("Prior knowledge of probability theory is expected of the reader.", ["Probability"]),
    ("The reader is expected to know statistics and basic matrix algebra.", ["Statistics", "Linear Algebra"]),
    ("Familiarity with optimisation and derivatives is assumed throughout.", ["Optimization", "Calculus"]),
    ("We assume a background in statistics and information theory.", ["Statistics", "Information Theory"]),
    ("Basic knowledge of probability is needed to follow Section 3.", ["Probability"]),
    ("Recall that the probability of an event is at most one.", []),
    ("The probability of each token is given by a softmax over the vocabulary.", []),
    ("Statistics of the training data are reported in Table 2.", []),
    ("We improve optimization of the loss with a new schedule.", []),
]


def _cases():
    return [{"sentence": s, "expected": e} for s, e in CASES]


def test_precision_and_recall_on_the_labelled_sentences():
    report = sp.evaluate(_cases())
    assert report["recall"] == 1.0 and report["precision"] == 1.0, report


def test_the_bare_names_count_only_in_a_sentence_with_an_explicit_cue():
    assert sp.find_in_sentence("Statistics of the training data are reported in Table 2.")["subjects"] == []
    assert sp.find_in_sentence("Recall that the probability of an event is at most one.")["subjects"] == []
    assert sp.find_in_sentence("We assume familiarity with probability.")["subjects"] == ["Probability"]


def test_a_negated_sentence_still_states_nothing():
    assert sp.find_in_sentence("No familiarity with probability or statistics is assumed.") == {"cue": None, "subjects": [], "concepts": []}
