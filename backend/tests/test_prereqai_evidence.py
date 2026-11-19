"""Evidence passages: exact quotations with page, section and stable ids, bounded and de-duplicated, kept through saving, tolerant of legacy sessions."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.evidence import MAX_PER_CONCEPT, build_evidence, passage_id
from backend.main import app
from backend.models import DetectedConcept, Paragraph
from backend.platform import platform
from backend.session import session_manager

pytestmark = pytest.mark.prereqai
SAMPLE = "examples/prerequisites/sample-paper.pdf"
PAGE = (Path(__file__).resolve().parents[1] / "web" / "index.html").read_text(encoding="utf-8")
client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def served(tmp_path, monkeypatch):
    monkeypatch.setenv("PREREQAI_SESSION_DIR", str(tmp_path))
    session_manager.sessions.clear()
    yield tmp_path
    session_manager.sessions.clear()


def fake(paragraphs, pages=(), concepts=("Softmax",)):
    return SimpleNamespace(paragraphs=paragraphs, pages=[SimpleNamespace(page_number=n, text=t) for n, t in pages],
                           concepts=[DetectedConcept(name=c, domain="x", occurrences=1) for c in concepts])


def test_every_quotation_is_an_exact_substring_of_the_page_it_cites(served):
    outcome = platform.analyze(SAMPLE)
    paper = session_manager.get(outcome["session_id"]).paper
    pages = {p.page_number: p.text for p in paper.pages}
    checked = 0
    for item in outcome["report"]["concept_evidence"]:
        for passage in item["passages"]:
            assert passage["sentence"] in pages[passage["page_number"]] and passage["section"] and passage["passage_id"] == passage_id(passage["section"], passage["sentence"])
            assert item["concept"] in passage["concepts"]
            checked += 1
    assert checked >= 5 and all(len(i["passages"]) <= MAX_PER_CONCEPT for i in outcome["report"]["concept_evidence"])


def test_a_sentence_missing_from_its_page_is_never_quoted():
    paragraphs = [Paragraph(1, "Method", "The softmax function turns scores into a distribution. It is applied to every row of the matrix.", 1)]
    found = build_evidence(fake(paragraphs, pages=[(1, "Something else entirely.")]))
    assert found == {}  # the paragraph says page 1, page 1 does not contain the sentence: nothing is invented
    text = "Preface line. The softmax function turns scores into a distribution. It is applied to every row of the matrix."
    found = build_evidence(fake([Paragraph(1, "Method", text[14:], 1)], pages=[(1, text)]))
    assert found["Softmax"][0]["sentence"] in text and found["Softmax"][0]["page_number"] == 1


def test_duplicates_are_removed_the_cap_holds_and_references_are_not_quoted():
    same = "The softmax function turns scores into a probability distribution."
    paragraphs = [Paragraph(i, "Method", f"{same} Sentence number {i} also uses the softmax of every score here.", None) for i in range(1, 7)]
    paragraphs.append(Paragraph(9, "References", "[1] Smith. The softmax function in a cited title appears here too, honestly.", None))
    passages = build_evidence(fake(paragraphs))["Softmax"]
    assert len(passages) == MAX_PER_CONCEPT == 3
    assert len({p["sentence"] for p in passages}) == 3 and sum(p["sentence"] == same for p in passages) == 1
    assert all(p["section"] != "References" for p in passages) and passages == build_evidence(fake(paragraphs))["Softmax"]  # deterministic ids and order


def test_instructional_sections_come_before_related_work():
    paragraphs = [Paragraph(1, "Related Work", "Earlier work applied the softmax function to speech recognition tasks.", None),
                  Paragraph(2, "Method", "We apply the softmax function to the attention scores of each head.", None)]
    assert [p["section"] for p in build_evidence(fake(paragraphs))["Softmax"]] == ["Method", "Related Work"]


def test_evidence_survives_saving_and_restoring_the_session(served):
    sid = platform.analyze(SAMPLE)["session_id"]
    before = session_manager.get(sid).report["concept_evidence"]
    session_manager.sessions.clear()  # a restart: only the saved file remains
    assert session_manager.get(sid).report["concept_evidence"] == before and before[0]["passages"]


def test_a_legacy_session_without_passages_or_pages_is_still_readable(served):
    sid = platform.analyze(SAMPLE)["session_id"]
    path = served / f"{sid}.session"
    saved = json.loads(path.read_bytes())

    def strip(value):
        if isinstance(value, dict):
            value.pop("passages", None)
            if value.get("c") == "backend.models.paper.Paragraph":
                value["f"].pop("page_number", None)
            for item in value.values():
                strip(item)
        elif isinstance(value, list):
            for item in value:
                strip(item)

    strip(saved)
    path.write_text(json.dumps(saved), encoding="utf-8")
    session_manager.sessions.clear()
    response = client.get(f"/api/session/{sid}")
    assert response.status_code == 200 and response.json()["session_id"] == sid
    paper = session_manager.get(sid).paper
    assert all(p.page_number is None for p in paper.paragraphs) and not any("passages" in c for c in session_manager.get(sid).report["concept_evidence"])
    legacy = build_evidence(paper)  # recomputed from the old paper: sentences without pages, never with invented ones
    assert legacy and all(p["page_number"] is None for ps in legacy.values() for p in ps)


def test_the_extractive_tutor_names_the_page_when_known_and_the_page_shows_the_passages():
    from backend.tutor.rule_based_tutor import RuleBasedTutor

    passage = {"section": "2 Method", "paragraph_id": 4, "text": "We apply softmax.", "coverage": 0.9}
    assert "2 Method\", page 3, paragraph 4" in RuleBasedTutor._extractive_answer([{**passage, "page_number": 3}])
    assert "page" not in RuleBasedTutor._extractive_answer([{**passage, "page_number": None}]).split("1. From")[1]  # a legacy session has none
    assert "passages" in PAGE and "blockquote" in PAGE and "passage_id" in PAGE
