"""BM25 tokens: hyphen parts and letter-digit terms are terms, and every real-paper miss gets a reproducible failure class."""
import pytest

from backend import retrieval
from backend.prereqai_eval import retrieval_real
from backend.platform import platform
from backend.session import session_manager

pytestmark = pytest.mark.prereqai


def test_hyphenated_compounds_also_give_their_parts():
    terms = retrieval._tokens("A grade-school task with chain-of-thought prompting.")
    assert {"grade-school", "grade", "school", "chain-of-thought", "chain", "thought"} <= set(terms)


def test_letter_digit_terms_are_kept_and_bare_numbers_are_not():
    terms = retrieval._tokens("Mistral 7B beats Llama 2 13B on T5 style tasks in 2022.")
    assert {"7b", "13b", "t5"} <= set(terms)
    assert not {"2", "2022", "7", "13"} & set(terms)


def test_a_question_and_a_paper_that_hyphenate_differently_still_share_terms():
    assert {"grade", "school"} <= set(retrieval._tokens("grade-school")) & set(retrieval._tokens("a school for grade level"))


@pytest.fixture(scope="module")
def papers():
    data = retrieval_real.load()
    paths = retrieval_real.pdf_paths(sorted({q["paper"] for q in data["questions"]}))
    return {pid: session_manager.get(platform.analyze(path)["session_id"]).paper for pid, path in paths.items()}


def test_every_real_paper_miss_gets_one_known_failure_class(papers):
    rows = retrieval_real.classify_failures(papers)
    assert rows and all(r["class"] in retrieval_real.FAILURE_CLASSES and r["detail"] for r in rows)
    assert rows == retrieval_real.classify_failures(papers)  # reproducible
    assert sum(retrieval_real.failure_summary(rows).values()) == len(rows)
    assert not any(r["class"] == "evidence_absent" for r in rows)  # every gold phrase is in the extracted text


def test_a_search_that_returns_nothing_is_classified_for_every_question(papers):
    rows = retrieval_real.classify_failures(papers, search=lambda paper, question, limit: [])
    assert len(rows) == retrieval_real.evaluate(papers)["questions"]


def test_the_token_change_does_not_lower_hybrid_recall_and_quotations_stay_exact(papers):
    hybrid = retrieval_real.evaluate(papers)["systems"]["hybrid"]
    assert hybrid["quotations_verified"] == 1.0 and hybrid["recall_at_k"] >= 0.66 and hybrid["mrr"] >= 0.50  # was 0.639 / 0.493
    assert hybrid["by_paper"]["mistral-7b"]["recall_at_k"] >= 0.5 and hybrid["by_paper"]["chain-of-thought"]["recall_at_k"] >= 0.33
