"""Retrieval-grounded answers: matching sentences of the paper are quoted with verified citations, a definition is followed by them when the question asks more, and the tutor abstains only without evidence. Questions are AI-written and PROVISIONAL."""
import pytest

from backend.prereqai_eval import answer_grounding, retrieval_real
from backend.platform import platform
from backend.session import TutorMode, session_manager

pytestmark = pytest.mark.prereqai


@pytest.fixture(scope="module")
def dpo():
    path = retrieval_real.pdf_paths({"dpo"})["dpo"]
    return session_manager.get(platform.analyze(path)["session_id"])


def _ask(session, question):
    result = platform.learning.answer(session=session, paper=session.paper, question=question, mode=TutorMode.INTUITION, topic=None)
    return result["responses"][0].answer


def test_a_why_question_that_names_a_concept_is_answered_from_the_paper_not_the_prerequisite_table(dpo):
    text = _ask(dpo, "Why does DPO not need a reward model?")
    assert "builds on Probability" not in text and "“" in text and "reward model" in text.lower()


def test_a_pure_definition_question_keeps_the_built_in_definition(dpo):
    text = _ask(dpo, "What is the Bradley-Terry model?")
    assert text.startswith("Bradley-Terry Model:") and "“" not in text


def test_a_definition_is_followed_by_the_papers_own_sentences_when_the_question_asks_more(dpo):
    text = _ask(dpo, "How does the Bradley-Terry model relate to the DPO loss?")
    assert "“" in text and "Bradley" in text


def test_an_unanswerable_question_abstains_instead_of_guessing(dpo):
    assert "could not find" in _ask(dpo, "How many moons does Jupiter have?").lower()


def test_every_quotation_is_exact_and_most_real_questions_show_their_gold_phrase():
    data = retrieval_real.load()
    sessions = {pid: platform.analyze(path)["session_id"] for pid, path in retrieval_real.pdf_paths({q["paper"] for q in data["questions"]}).items()}
    report = answer_grounding.evaluate(sessions, data)
    assert report["citations_verified"] == 1.0 and report["contains_gold"] >= 24 and report["off_target"] <= 2 and report["status"] == "ai_written_unreviewed"
