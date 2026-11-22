"""The real-paper retrieval evaluation: a documented question set over the six licensed PDFs, recall@5 and MRR for both searches, exact quotations, and a gate that compares systems without inventing floors."""
from types import SimpleNamespace

import pytest

from backend.prereqai_eval import gate, retrieval_real as rr

pytestmark = pytest.mark.prereqai
IDS = {"dpo", "mixtral", "chain-of-thought", "constitutional-ai", "gqa", "mistral-7b"}


def test_the_question_set_covers_six_papers_with_gold_phrases_and_says_who_wrote_it():
    data = rr.load()
    assert len(data["questions"]) >= 30 and {q["paper"] for q in data["questions"]} == IDS and len({q["id"] for q in data["questions"]}) == len(data["questions"])
    assert all(q["question"].endswith("?") and q["gold"].strip() and q["style"] in ("clean", "loose") for q in data["questions"])
    assert data["status"] == "ai_written_unreviewed" and "NOT reviewed by a human" in data["provenance"]
    assert set(rr.pdf_paths(IDS)) == IDS  # every PDF is shipped (their licences are recorded in the manifests)


def test_a_hit_ignores_case_spaces_and_punctuation_and_rank_is_one_based():
    passages = [{"sentence": "Nothing here."}, {"sentence": "The Bradley - Terry   model is used."}]
    assert rr.rank_of(passages, "bradley-terry model") == 2 and rr.rank_of(passages, "absent phrase") is None and rr.key("A-b C.") == "abc"


def fake_paper(text):
    return SimpleNamespace(pages=[SimpleNamespace(page_number=1, text=text)])


def test_recall_and_mrr_are_computed_per_paper_and_quotations_are_checked():
    papers = {"dpo": fake_paper("The Bradley-Terry model is used. Other text. KL constraint keeps it near.")}
    data = {"status": "x", "provenance": "p", "questions": [{"id": "1", "paper": "dpo", "question": "q1", "gold": "Bradley-Terry model", "style": "clean"},
                                                            {"id": "2", "paper": "dpo", "question": "q2", "gold": "KL constraint", "style": "loose"}, {"id": "3", "paper": "gqa", "question": "q3", "gold": "x", "style": "clean"}]}
    first, second = {"sentence": "The Bradley-Terry model is used.", "page_number": 1}, {"sentence": "KL constraint keeps it near.", "page_number": 1}
    searches = {"lexical": lambda paper, q, k: [first] if q == "q1" else [], "hybrid": lambda paper, q, k: [first, second] if q == "q1" else [{"sentence": "zzz"}, second]}
    report = rr.evaluate(papers, data, searches=searches)
    assert report["questions"] == 2 and report["papers"] == ["dpo"] and report["gold_in_text"] == 1.0  # the gqa question is left out: its paper was not given
    lexical, hybrid = report["systems"]["lexical"], report["systems"]["hybrid"]
    assert (lexical["recall_at_k"], lexical["mrr"]) == (0.5, 0.5) and (hybrid["recall_at_k"], hybrid["mrr"]) == (1.0, 0.75)
    assert hybrid["by_paper"]["dpo"] == {"questions": 2, "recall_at_k": 1.0, "mrr": 0.75} and lexical["quotations_verified"] == 1.0 and hybrid["quotations_verified"] == 0.75


def test_the_gate_compares_the_systems_per_paper_and_holds_no_invented_recall_floor(monkeypatch):
    class Pipeline:
        def run(self, path):
            return SimpleNamespace(paper=fake_paper("text"))

    monkeypatch.setattr("backend.pipeline.ResearchPaperPipeline", Pipeline)
    monkeypatch.setattr(rr, "evaluate", lambda papers, data=None, **k: {"questions": 36, "k": 5, "gold_in_text": 0.9, "papers": ["dpo", "gqa"], "systems": {
        "lexical": {"recall_at_k": 0.4, "mrr": 0.3, "quotations_verified": 1.0, "by_paper": {"dpo": {"recall_at_k": 0.5, "mrr": 0.4}, "gqa": {"recall_at_k": 0.5, "mrr": 0.4}}},
        "hybrid": {"recall_at_k": 0.45, "mrr": 0.3, "quotations_verified": 1.0, "by_paper": {"dpo": {"recall_at_k": 0.67, "mrr": 0.4}, "gqa": {"recall_at_k": 0.33, "mrr": 0.4}}}}})
    checks = []
    gate.real_retrieval_checks(checks, {"questions": 30})
    by_metric = {c["metric"]: c for c in checks}
    assert by_metric["hybrid_not_below_lexical:dpo"]["passed"] and not by_metric["hybrid_not_below_lexical:gqa"]["passed"]  # a paper where hybrid does worse is reported as a failure, not hidden
    assert by_metric["quotations_verified"]["passed"] and by_metric["questions"]["passed"] and not any("recall_at_k" in m for m in by_metric)
    assert all(c["group"] == "retrieval_real" for c in checks)
