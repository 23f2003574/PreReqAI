import pytest

from backend import mastery_model
from backend.tutor import diagnostic
from backend.tutor.quiz_bank import QUIZ_BANK, QUIZ_EXPLANATIONS, unexplained_questions
from backend.tutor.quiz_bank_depth import THIRD_ROWS

pytestmark = pytest.mark.prereqai
TARGETS = [row[0] for row in THIRD_ROWS]
STOP = set("a an the of in on to is are does do what why how which when and or for with that it its as by at be from this".split())


def test_the_targets_are_the_concepts_the_six_real_papers_mention():
    from backend.prereqai_eval import gate, retrieval_real

    data = retrieval_real.load()
    papers = gate._real_papers({q["paper"] for q in data["questions"]})
    detected = {c.name for paper in papers.values() for c in paper.concepts}
    assert all(len(QUIZ_BANK[name]) >= 3 for name in detected), [n for n in detected if len(QUIZ_BANK[n]) < 3]


def test_each_target_has_three_different_questions_with_an_explanation():
    assert len(TARGETS) == len(set(TARGETS)) >= 35
    for name in TARGETS:
        items = QUIZ_BANK[name]
        assert len(items) >= 3 and len({i["question"] for i in items}) == len(items) and len({i["answer"] for i in items}) == len(items), name
        assert all(QUIZ_EXPLANATIONS.get((name, i["question"])) for i in items), name


def test_third_questions_do_not_restate_an_earlier_question_or_answer():
    for name, question, answer, *_ in THIRD_ROWS:
        earlier = QUIZ_BANK[name][:-1] if QUIZ_BANK[name][-1]["question"] == question else QUIZ_BANK[name][:2]
        for item in earlier:
            assert answer.lower() not in item["answer"].lower() and item["answer"].lower() not in answer.lower(), (name, question)
            words = lambda text: {w.strip("?.,'") for w in text.lower().split()} - STOP - {w.lower() for w in name.replace("-", " ").split()}
            a, b = words(question), words(item["question"])
            assert len(a & b) / max(1, len(a | b)) < 0.5, (name, question, item["question"])


def test_no_question_has_weak_distractors_and_every_question_is_explained():
    assert diagnostic.distractor_report()["weak"] == [] and unexplained_questions() == []


def test_fresh_distinct_evidence_reaches_the_mastery_threshold_without_repeats():
    answers = [(True, "medium", f"Softmax:{n}") for n in (1, 2, 3)] + [(True, "medium", "Softmax:1")]  # three different questions, one retry
    times = [None] * 4
    from datetime import datetime, timedelta, timezone

    start = datetime(2026, 11, 1, tzinfo=timezone.utc)
    times = [start, start + timedelta(hours=1), start + timedelta(days=2), start + timedelta(days=3)]
    result = mastery_model.estimate(answers, times)
    assert result["effective_answers"] >= mastery_model.MIN_EFFECTIVE and result["mastered"], result
    two_questions = mastery_model.estimate([(True, "medium", "Softmax:1"), (True, "medium", "Softmax:2")], times[:2])
    assert two_questions["effective_answers"] < mastery_model.MIN_EFFECTIVE
