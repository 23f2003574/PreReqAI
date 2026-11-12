"""Every registered concept has practice questions, and a quiz on something PreReqAI does not know is not answered with other topics."""
import pytest

from backend.concepts.concept_registry import ConceptRegistry
from backend.tutor.quiz_bank import QUIZ_BANK
from backend.tutor.rule_based_tutor import RuleBasedTutor

pytestmark = pytest.mark.prereqai

NAMES = [c.name for c in ConceptRegistry().all()]


class _Concept:
    def __init__(self, name):
        self.name = name


class _Paper:
    concepts = [_Concept("Softmax"), _Concept("Attention")]


class _Session:
    active_concept = None


def _quiz(question):
    return RuleBasedTutor._quiz_answer(_Paper(), _Session(), question)


def test_every_registry_concept_has_questions_and_the_bank_names_only_registry_concepts():
    assert [n for n in NAMES if n not in QUIZ_BANK] == [] and set(QUIZ_BANK) <= set(NAMES)


def test_every_question_is_well_formed_and_unique():
    questions = []
    for name, items in QUIZ_BANK.items():
        for item in items:
            assert set(item) == {"question", "answer", "difficulty"} and item["difficulty"] in {"Easy", "Medium", "Hard"}
            assert item["question"].endswith(("?", ".")) and item["answer"].endswith(".") and len(item["answer"].split()) >= 5
            questions.append(item["question"])
    assert len(questions) == len(set(questions))


@pytest.mark.parametrize("name", NAMES)
def test_a_quiz_on_each_registry_concept_returns_its_own_questions(name):
    answer = _quiz(f"Quiz me on {name}")
    assert answer.startswith(f"{name} Q1 (") and "no practice questions" not in answer


@pytest.mark.parametrize("question", ["Quiz me on Quantum Gravity", "test me about thermal conductivity", "Quiz me on blockchain"])
def test_an_unknown_topic_is_declined_not_answered_with_other_concepts(question):
    answer = _quiz(question)
    assert answer.startswith("I can't quiz you on") and " Q1 (" not in answer


@pytest.mark.parametrize("question", ["Quiz me", "Quiz me on this paper", "quiz me on the paper so far", "Quiz me on it"])
def test_generic_quiz_requests_still_use_the_papers_concepts(question):
    answer = _quiz(question)
    assert "Softmax Q1" in answer and "Attention Q1" in answer and "can't quiz" not in answer


def test_a_known_prerequisite_without_questions_keeps_its_own_message():
    assert _quiz("Quiz me on Calculus") == "There are no practice questions yet for Calculus."
