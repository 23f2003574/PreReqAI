"""The prerequisite reading list: ranking by citation frequency and section, no bibliography double counting, determinism, unresolved references, API and page."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.models import Citation, DetectedConcept, Paragraph, PaperReference, RelatedPaper
from backend.parsing.citation_extractor import CitationExtractor
from backend.reading_list import build_reading_list, identifiers, section_weight
from backend.platform import platform
from backend.session import session_manager
from types import SimpleNamespace

pytestmark = pytest.mark.prereqai
PAGE = (Path(__file__).resolve().parents[1] / "web" / "index.html").read_text(encoding="utf-8")
client = TestClient(app, raise_server_exceptions=False)
SAMPLE = "examples/prerequisites/sample-paper.pdf"

REFS = {1: "A. Author. Neural machine translation by jointly learning to align. arXiv:1409.0473, 2014.",
        2: "B. Writer. Deep residual learning. https://arxiv.org/abs/1512.03385 2015.",
        3: "C. Scholar. A journal paper. doi:10.1145/3065386. 2017.",
        4: "D. Obscure. A tech report nobody can find. 2012.",
        5: "E. Other. An experiments-only citation. arXiv:1706.03762v5 2017."}


def paper(paragraphs, references=REFS, concepts=("Attention", "Softmax")):
    built = SimpleNamespace(paragraphs=[Paragraph(i, title, text) for i, (title, text) in enumerate(paragraphs, 1)],
                            references=[PaperReference(n, t) for n, t in references.items()],
                            related_papers=[RelatedPaper(n, t.split(". ")[1], [t.split(". ")[0]], 2015, "cites", None) for n, t in references.items() if ". " in t],
                            concepts=[DetectedConcept(name=c, domain="x", occurrences=2) for c in concepts])
    return CitationExtractor().extract(built)


PARAGRAPHS = [
    ("1 Introduction", "Attention was introduced for translation [1]. We also build on residual networks [2]. See [1, 3] for background."),
    ("2 Related Work", "Residual connections were studied in [2]. Other work [3] used softmax outputs."),
    ("3 Method", "The softmax over attention scores follows [1]."),
    ("4 Experiments", "We compare with [5] and again with [5] and with [4]."),
    ("References", "[1] A. Author. Neural machine translation. [2] B. Writer. Deep residual learning. [3] [4] [5]"),
]


def test_references_are_ranked_by_where_and_how_often_they_are_cited_and_the_bibliography_is_not_counted():
    items = build_reading_list(paper(PARAGRAPHS))
    assert [i["reference_number"] for i in items] == [1, 3, 2, 5, 4]  # 2 and 3 tie on score; 3's citing sentences name a concept
    first = items[0]
    assert first["citations"] == 3 and first["score"] == 3 + 3 + 2 and first["sections"] == {"1 Introduction": 2, "3 Method": 1}  # the bibliography's "[1]" is not a citation
    assert items[3]["citations"] == 2 and items[3]["score"] == 2 and items[4]["score"] == 1
    assert first["concepts"][0] == "Attention" and "Attention" in first["reason"] and "3 times" in first["reason"]
    assert [i["rank"] for i in items] == [1, 2, 3, 4, 5]


def test_the_order_is_deterministic_and_limited():
    built = paper(PARAGRAPHS)
    assert build_reading_list(built) == build_reading_list(built) and len(build_reading_list(built, limit=2)) == 2
    tied = paper([("3 Method", "We use [4] and [3] and [2].")])
    assert [i["reference_number"] for i in build_reading_list(tied)] == [2, 3, 4]  # equal scores: the lower reference number first


def test_identifiers_come_only_from_the_reference_text_and_unresolved_ones_are_labelled():
    items = {i["reference_number"]: i for i in build_reading_list(paper(PARAGRAPHS))}
    assert (items[1]["arxiv_id"], items[1]["source"], items[1]["status"]) == ("1409.0473", "arXiv:1409.0473", "resolvable")
    assert items[2]["arxiv_id"] == "1512.03385" and items[3]["doi"] == "10.1145/3065386" and items[3]["source"] == "10.1145/3065386"
    assert items[5]["arxiv_id"] == "1706.03762v5"
    assert items[4]["status"] == "unresolved" and items[4]["source"] is None and items[4]["arxiv_id"] is None and "cannot be opened from here" in items[4]["reason"]
    assert items[4]["reference"].startswith("D. Obscure") and identifiers("nothing here 2012") == (None, None)


def test_missing_metadata_is_not_invented_and_unknown_numbers_and_empty_papers_are_handled():
    bare = paper([("1 Introduction", "We cite [1] and [9].")], references={1: "No structure at all"}, concepts=())
    bare.related_papers = []
    [item] = build_reading_list(bare)  # [9] is not in the bibliography: not listed
    assert item["title"] is None and item["authors"] == [] and item["year"] is None and item["reference"] == "No structure at all" and item["concepts"] == []
    assert "no detected concept" in item["reason"]
    assert build_reading_list(paper([("1 Introduction", "No citations here.")])) == [] and build_reading_list(SimpleNamespace()) == []


def test_section_weights_favour_foundational_sections():
    assert section_weight("1 Introduction") == section_weight("II. Background") == section_weight("Preliminaries") == 3
    assert section_weight("3 Method") == 2 and section_weight("4 Experiments") == 1 == section_weight("Related Work") == section_weight(None)


@pytest.fixture
def sid(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    session_manager.sessions.clear()
    yield platform.analyze(SAMPLE)["session_id"]
    session_manager.sessions.clear()


def test_the_api_lists_the_reading_list_without_fetching_anything(sid, monkeypatch):
    import socket

    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: pytest.fail("the reading list must not touch the network"))
    body = client.get(f"/api/session/{sid}/reading-list").json()
    assert body["status"] == "success" and isinstance(body["reading_list"], list) and len(body["reading_list"]) <= 10
    assert client.get(f"/api/session/{sid}/reading-list", params={"limit": 0}).status_code == 422
    assert client.get("/api/session/nope/reading-list").status_code == 404
    session = session_manager.get(sid)
    session.paper = paper(PARAGRAPHS)  # a paper with citations: the same endpoint
    items = client.get(f"/api/session/{sid}/reading-list", params={"limit": 2}).json()["reading_list"]
    assert [i["reference_number"] for i in items] == [1, 3] and items[0]["source"] == "arXiv:1409.0473"


def test_the_page_shows_the_list_and_only_analyses_a_work_on_an_explicit_choice():
    assert 'id="readingBtn"' in PAGE and "/reading-list" in PAGE and "Analyse this next" in PAGE and "loadReadingList" in PAGE
    assert PAGE.count('fetch("/api/session/" + encodeURIComponent(state.sid) + "/reading-list")') == 1 and 'addEventListener("click", loadReadingList)' in PAGE  # fetched on a click, never automatically
