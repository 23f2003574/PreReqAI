"""Sentences that merely contain "=" and bibliography lines were reported as equations (and so reached the report, the knowledge
graph and the tutor's equation answers). Genuine formulas must still be extracted."""
from types import SimpleNamespace as N

import pytest

from backend.parsing.equation_extractor import EquationExtractor, looks_like_prose

PROSE = [
    "where x = 5 is the number of users.",
    "We set learning rate = 0.1 in Section 4.",
    "Experiments on CIFAR-10 achieve accuracy = 94%.",
    "the batch size = 32 and we train it",
]

FORMULAS = [
    "w = w - lr * g",
    "p = softmax(z)",
    "A = softmax(QK^T)",
    "Softmax(x) = exp(x)/sum exp   (3)",
    "$x = W y + b$ (1)",
    "Attention(Q, K, V) = softmax(QK^T / sqrt(d_k)) V   (1)",
    "f(x) = x if x > 0 else 0",
    "x = 1, for all i in S.",
    "y_1 =",
]


def _extract(sections):
    paper = N(sections=[N(title=title, content=content) for title, content in sections])
    return EquationExtractor().extract(paper).equations


@pytest.mark.parametrize("line", PROSE)
def test_a_sentence_containing_an_equals_sign_is_prose(line):
    assert looks_like_prose(line)


@pytest.mark.parametrize("line", FORMULAS)
def test_formulas_are_not_prose(line):
    assert not looks_like_prose(line)


def test_only_formulas_are_extracted_from_a_section_mixing_both():
    content = "\n".join([PROSE[0], FORMULAS[0], PROSE[1], FORMULAS[3], PROSE[2]])
    equations = _extract([("Method", content)])
    assert [e.expression for e in equations] == [FORMULAS[0], FORMULAS[3]]
    assert [e.equation_id for e in equations] == [1, 2]  # ids stay consecutive after filtering
    assert {e.section for e in equations} == {"Method"}


@pytest.mark.parametrize("title", ["References", "7 References", "VII. Bibliography", "References:"])
def test_the_bibliography_holds_no_equations(title):
    assert _extract([("Method", "a = b"), (title, "[1] Smith. Title of a paper, vol = 3.\nx = y")]) \
        == _extract([("Method", "a = b")])
    assert [e.section for e in _extract([("Method", "a = b"), (title, "x = y")])] == ["Method"]
