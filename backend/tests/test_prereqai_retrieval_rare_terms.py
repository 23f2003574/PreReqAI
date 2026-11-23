"""Retrieval admits a passage that matches only one query term when that term is rare in the paper (a distinctive name or technique), never when the term is common, and still verifies every quotation."""
from types import SimpleNamespace

import pytest

from backend import retrieval
from backend.models import Paper, Paragraph, PaperSection
from backend.prereqai_eval import retrieval_real
from backend.tests.test_prereqai_retrieval import sentence

pytestmark = pytest.mark.prereqai


def long_paper(extra=()):
    paper = Paper(source_path="s.pdf", metadata=None)
    paper.paragraphs, pages = [], {}
    for p in range(1, 41):
        text = " ".join(sentence(p * 3 + k) for k in range(3))
        text = " ".join([text, *(extra if p == 7 else ())])
        paper.paragraphs.append(Paragraph(p, "3 Method", text, p))
        pages[p] = text
    paper.pages = [SimpleNamespace(page_number=n, text=t) for n, t in pages.items()]
    paper.sections, paper.concepts = [PaperSection(title="3 Method", content="x")], []
    return paper


RARE = "The chunking scheme splits a long sequence into overlapping windows before encoding."


def test_a_question_matching_one_rare_term_finds_its_sentence_and_the_quotation_is_exact():
    paper = long_paper([RARE])
    found = retrieval.bm25_search(paper, "How does chunking work in practice nowadays?", 5)
    assert [p["sentence"] for p in found] == [RARE] and found[0]["page_number"] == 7 and RARE in paper.pages[6].text


def test_a_question_matching_only_a_common_term_still_finds_nothing():
    paper = long_paper([RARE])
    assert retrieval.bm25_search(paper, "What about turbines in practice nowadays?", 5) == []
    assert retrieval.bm25_search(paper, "How does zzzz work in practice nowadays?", 5) == []


def test_short_terms_and_tiny_papers_never_qualify_as_rare():
    assert retrieval.RARE_MIN_CHARS >= 5
    paper = long_paper(["The gpu runs it."])
    assert retrieval.bm25_search(paper, "Why does the gpu matter nowadays in practice?", 5) == []
    tiny = long_paper([RARE])
    tiny.paragraphs, tiny.pages = tiny.paragraphs[:2], tiny.pages[:2]
    assert retrieval.bm25_search(tiny, "How does chunking work in practice nowadays?", 5) == []


def test_the_real_paper_benchmark_does_not_fall_below_the_earlier_hybrid_numbers_per_paper():
    from backend.platform import platform
    from backend.session import session_manager
    data = retrieval_real.load()
    found = retrieval_real.pdf_paths(sorted({q["paper"] for q in data["questions"]}))
    loaded = {pid: session_manager.get(platform.analyze(path)["session_id"]).paper for pid, path in found.items()}
    result = retrieval_real.evaluate(loaded)["systems"]
    before = {"chain-of-thought": 0.167, "constitutional-ai": 0.833, "dpo": 0.5, "gqa": 0.833, "mistral-7b": 0.333, "mixtral": 0.833}  # hybrid recall@5 before this change (after the sentence fix)
    assert result["hybrid"]["quotations_verified"] == 1.0 and result["hybrid"]["recall_at_k"] >= 0.62
    for paper_id, row in result["hybrid"]["by_paper"].items():
        assert row["recall_at_k"] >= before[paper_id] - 1e-9 and row["recall_at_k"] >= result["lexical"]["by_paper"][paper_id]["recall_at_k"] - 1e-9
