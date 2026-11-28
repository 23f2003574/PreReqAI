"""Every registry concept has three different questions, each explained, with usable distractors."""
import pytest

from backend.concepts.concept_registry import ConceptRegistry
from backend.tutor import diagnostic, quiz_bank
from backend.tutor.quiz_session import ASKABLE

pytestmark = pytest.mark.prereqai


def test_all_registry_concepts_have_three_distinct_explained_questions():
    names = [c.name for c in ConceptRegistry().all()]
    assert len(names) >= 116
    for name in names:
        items = ASKABLE[name]
        assert len(items) >= 3, name
        assert len({i["question"] for i in items}) == len(items) and len({i["answer"] for i in items}) == len(items), name
    assert quiz_bank.unexplained_questions() == []
    assert diagnostic.distractor_report()["weak"] == []


def test_the_new_questions_are_not_rewordings_of_the_earlier_ones():
    import re

    def words(text):
        return set(re.findall(r"[a-z]{4,}", text.lower()))

    for name, items in ASKABLE.items():
        if name.startswith("Math: ") or len(items) < 3:
            continue
        last = items[-1]
        for earlier in items[:-1]:
            union = words(last["question"]) | words(earlier["question"])
            assert len(words(last["question"]) & words(earlier["question"])) / len(union) < 0.7, (name, last["question"])
