"""Reciprocal-rank fusion of the lexical and BM25 searches, and the rare-term gate."""
import pytest

from backend import retrieval

pytestmark = pytest.mark.prereqai


def test_fusion_scores_passages_found_by_both_searches_above_single_hits(monkeypatch):
    def passage(i):
        return {"passage_id": f"p{i}", "sentence": f"S{i}", "page_number": 1, "section": "Body", "concepts": []}

    monkeypatch.setattr("backend.tutor.grounding.search_evidence", lambda paper, question, limit: [passage(1), passage(2), passage(3)])
    monkeypatch.setattr(retrieval, "bm25_search", lambda paper, question, limit=5: [passage(3), passage(4)])
    monkeypatch.setattr(retrieval, "_with_context", lambda paper, found, limit: found)
    ids = [p["passage_id"] for p in retrieval.hybrid_search(object(), "q", limit=4)]
    assert ids[0] == "p3" and set(ids) == {"p1", "p2", "p3", "p4"}  # p3 is in both lists; BM25 is consulted even though the lexical search found enough


def test_a_short_single_rare_term_passes_the_gate_and_exact_quotations_hold():
    from backend.prereqai_eval import gate, retrieval_real

    data = retrieval_real.load()
    papers = gate._real_papers({q["paper"] for q in data["questions"]})
    hybrid = retrieval_real.evaluate(papers, data)["systems"]["hybrid"]
    assert hybrid["quotations_verified"] == 1.0 and hybrid["recall_at_k"] >= 0.74 and hybrid["mrr"] >= 0.57
