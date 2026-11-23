"""Hybrid retrieval offers the neighbouring sentence of its best passages as context (after every ranked passage, exact quotations) and admits a term that is distinctive for the paper."""
import pytest

from backend import retrieval
from backend.prereqai_eval import retrieval_real
from backend.tests.test_prereqai_retrieval_rare_terms import RARE, long_paper
from backend.platform import platform
from backend.session import session_manager

pytestmark = pytest.mark.prereqai

ANSWER = "Its overlap between windows is set to half the window length."


def test_the_next_sentence_follows_the_ranked_passages_and_is_an_exact_stored_sentence():
    paper = long_paper([RARE, ANSWER])
    found = retrieval.hybrid_search(paper, "How does chunking work in practice nowadays?", 5)
    sentences = [p["sentence"] for p in found]
    assert sentences[0] == RARE and ANSWER in sentences[1:]
    context = [p for p in found if p.get("context")]
    assert context and all(p["sentence"] in paper.pages[p["page_number"] - 1].text for p in found)
    assert sentences.index(ANSWER) > 0 and not found[0].get("context")


def test_context_never_displaces_a_ranked_passage_or_exceeds_the_limit():
    paper = long_paper([RARE, ANSWER])
    assert [p["sentence"] for p in retrieval.hybrid_search(paper, "How does chunking work in practice nowadays?", 1)] == [RARE]
    assert len(retrieval.hybrid_search(paper, "How does chunking work in practice nowadays?", 3)) <= 3


def test_nothing_found_means_no_context_either():
    assert retrieval.hybrid_search(long_paper([RARE]), "How does zzzz work in practice nowadays?", 5) == []


def test_a_term_in_more_than_the_distinctive_share_of_sentences_is_still_not_enough():
    assert retrieval.RARE_SHARE <= 0.10
    assert retrieval.bm25_search(long_paper([RARE]), "What about turbines in practice nowadays?", 5) == []


@pytest.fixture(scope="module")
def result():
    data = retrieval_real.load()
    paths = retrieval_real.pdf_paths(sorted({q["paper"] for q in data["questions"]}))
    papers = {pid: session_manager.get(platform.analyze(path)["session_id"]).paper for pid, path in paths.items()}
    return retrieval_real.evaluate(papers)["systems"]


def test_real_paper_hybrid_recall_improves_over_the_token_commit_and_stays_exact(result):
    hybrid = result["hybrid"]  # 0.667 recall@5 and 0.512 MRR before this change; the 36 questions are AI-written and unreviewed
    assert hybrid["quotations_verified"] == 1.0 and hybrid["recall_at_k"] >= 0.72 and hybrid["mrr"] >= 0.53
    assert hybrid["by_paper"]["mistral-7b"]["recall_at_k"] >= 0.5 and hybrid["by_paper"]["chain-of-thought"]["recall_at_k"] >= 0.33


def test_hybrid_stays_at_least_as_good_as_lexical_on_every_paper(result):
    for paper_id, row in result["hybrid"]["by_paper"].items():
        assert row["recall_at_k"] >= result["lexical"]["by_paper"][paper_id]["recall_at_k"] - 1e-9
