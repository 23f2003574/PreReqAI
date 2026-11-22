"""Diagnostic options: unique, fixed, drawn from the same concept and its neighbours, not given away by length, and weak items are reported."""
import pytest

from backend.tutor import diagnostic
from backend.tutor.misconception_registry import COMMON_MISCONCEPTIONS
from backend.tutor.quiz_session import ASKABLE, _lookup

pytestmark = pytest.mark.prereqai
IDS = [f"{concept}:{number}" for concept, items in ASKABLE.items() for number in range(1, len(items) + 1)]


def test_every_question_has_four_unique_options_in_a_fixed_order_and_ids_still_resolve():
    for identifier in IDS:
        options = diagnostic.options_for(identifier)
        assert len(options) == 4 and len({" ".join(o.lower().split()) for o in options}) == 4 and options == diagnostic.options_for(identifier)
        assert _lookup(identifier)[2]["answer"] in options


def test_distractors_come_from_the_same_concept_its_misconceptions_or_its_neighbours():
    for identifier in IDS:
        concept, correct = identifier.rpartition(":")[0], _lookup(identifier)[2]["answer"]
        related, _, _ = diagnostic.distractor_pool(identifier)
        neighbours = {a["answer"] for name in [concept, *diagnostic._siblings(concept)] for a in ASKABLE.get(name, [])} | set(COMMON_MISCONCEPTIONS.get(concept, []))
        assert set(related) <= neighbours and correct not in related
        if not diagnostic.weak_distractors(identifier):
            assert set(diagnostic.options_for(identifier)) - {correct} <= set(related)


def test_the_correct_answer_is_not_systematically_the_longest_option():
    longest = sum(max(diagnostic.options_for(i), key=len) == _lookup(i)[2]["answer"] for i in IDS)
    shortest = sum(min(diagnostic.options_for(i), key=len) == _lookup(i)[2]["answer"] for i in IDS)
    assert longest / len(IDS) <= 0.30 and shortest / len(IDS) <= 0.40  # four options: chance is 0.25


def test_the_correct_position_is_spread_over_the_options():
    positions = [diagnostic.options_for(i).index(_lookup(i)[2]["answer"]) for i in IDS]
    assert all(positions.count(p) / len(IDS) >= 0.10 for p in range(4))


def test_weak_questions_are_reported_not_hidden(monkeypatch):
    report = diagnostic.distractor_report()
    assert report["questions"] == len(IDS) and report["weak"] == [i for i in IDS if diagnostic.weak_distractors(i)]
    monkeypatch.setattr(diagnostic, "_siblings", lambda concept: [])
    monkeypatch.setitem(ASKABLE, "Lonely", [{"question": "Q?", "answer": "A one-of-a-kind answer."}])
    assert diagnostic.weak_distractors("Lonely:1") is True and "Lonely" in diagnostic.distractor_report()["concepts_without_related"]
