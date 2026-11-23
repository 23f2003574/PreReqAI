"""The gate holds absolute floors for hybrid retrieval on the real papers: the current search passes them, a deliberately degraded retriever fails them, and each failing paper is named."""
import pytest

from backend.prereqai_eval import gate, retrieval_real
from backend.platform import platform
from backend.retrieval import hybrid_search
from backend.session import session_manager

pytestmark = pytest.mark.prereqai


@pytest.fixture(scope="module")
def papers():
    data = retrieval_real.load()
    paths = retrieval_real.pdf_paths(sorted({q["paper"] for q in data["questions"]}))
    return {pid: session_manager.get(platform.analyze(path)["session_id"]).paper for pid, path in paths.items()}


def run(papers, hybrid):
    report = retrieval_real.evaluate(papers, searches={"lexical": lambda paper, question, limit: [], "hybrid": hybrid})
    checks = []
    gate.absolute_retrieval_checks(checks, report, gate.load_thresholds()["retrieval_real"])
    return checks


def test_the_current_hybrid_search_meets_every_absolute_floor(papers):
    checks = run(papers, lambda paper, question, limit: hybrid_search(paper, question, limit))
    assert len(checks) == 2 + 6 and all(c["passed"] for c in checks), [c for c in checks if not c["passed"]]


def test_a_retriever_that_returns_nothing_or_the_wrong_sentences_fails_the_floors_and_names_the_papers(papers):
    nothing = run(papers, lambda paper, question, limit: [])
    assert not any(c["passed"] for c in nothing if c["metric"] in ("hybrid_recall_at_k", "hybrid_mrr")) and {c["metric"] for c in nothing if not c["passed"]} >= {"hybrid_recall_at_k", "hybrid_mrr", "hybrid_recall:mixtral"}
    from backend.evidence import quotable_sentences
    first = lambda paper, question, limit: [{"sentence": s, "page_number": n, "passage_id": "x", "section": sec, "concepts": []} for _, _, _, sec, s, n in quotable_sentences(paper)[:limit]]
    wrong = run(papers, first)
    assert not all(c["passed"] for c in wrong) and any(c["metric"].startswith("hybrid_recall:") and not c["passed"] for c in wrong)


def test_every_floor_is_in_thresholds_and_below_the_measured_numbers_in_the_readme():
    floors = gate.load_thresholds()["retrieval_real"]
    assert set(floors["hybrid_recall_by_paper"]) == {"chain-of-thought", "constitutional-ai", "dpo", "gqa", "mistral-7b", "mixtral"}
    assert 0 < floors["hybrid_recall_at_k"] < 0.639 and 0 < floors["hybrid_mrr"] < 0.493
