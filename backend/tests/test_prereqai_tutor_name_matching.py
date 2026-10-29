"""The one whole-word rule the tutor uses to find a concept in a question: separators are normalised, a plural s is
optional where wanted, and a name inside a longer word never matches."""
import re

import pytest

from backend.tutor.rule_based_tutor import _name_pattern, _normalise

pytestmark = pytest.mark.prereqai


def _found(name, question, **options):
    return bool(re.search(_name_pattern(name, **options), _normalise(question)))


def test_matches_whole_words_case_and_separator_insensitively():
    assert _found("Self-Attention", "What is self attention?")
    assert _found("Linear Algebra", "why LINEAR_ALGEBRA?")


def test_plural_is_optional_and_can_be_switched_off():
    assert _found("Transformer", "How do transformers work?")
    assert not _found("Transformer", "How do transformers work?", plural=False)


def test_a_name_inside_a_longer_word_does_not_match():
    assert not _found("Probability", "an improbable event")
    assert not _found("Attention", "inattention")
    assert not _found("Graphs", "paragraphs are long")
