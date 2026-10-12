"""Concept matching in questions is whole-word: no answers triggered by words that merely contain a concept name."""
import pymupdf
import pytest
from starlette.testclient import TestClient

from backend.main import app

PLACEHOLDER = "tutoring model has not yet been configured"


def _session(tmp_path, text):
    path = tmp_path / "paper.pdf"
    doc = pymupdf.open()
    doc.new_page().insert_textbox(pymupdf.Rect(72, 72, 540, 760), text, fontsize=10)
    doc.save(path)
    client = TestClient(app)
    with open(path, "rb") as handle:
        sid = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")}).json()["session_id"]
    return client, sid


def _answers(client, sid, question):
    body = client.post(f"/api/session/{sid}/question", json={"question": question}).json()
    return [r["answer"] for r in body["responses"]]


GRAPH = "Abstract\nA graph neural network with message passing and a policy gradient agent.\n"


@pytest.mark.parametrize("question", ["Summarize the paragraphs", "What is the improbability of this?", "Is the multigraphs section important?"])
def test_a_word_containing_a_concept_name_does_not_trigger_its_answer(tmp_path, question):
    client, sid = _session(tmp_path, GRAPH)
    assert all(PLACEHOLDER in a for a in _answers(client, sid, question))


@pytest.mark.parametrize("question", ["What are graphs?", "Why do I need GRAPHS", "graphs, please"])
def test_the_concept_name_as_a_word_still_answers_including_plurals_and_case(tmp_path, question):
    client, sid = _session(tmp_path, GRAPH)
    assert any("adjacency" in a for a in _answers(client, sid, question))


def test_a_compound_name_answers_for_itself_not_for_the_name_inside_it(tmp_path):
    client, sid = _session(tmp_path, "Abstract\nMulti-head attention and self-attention in a transformer.\n")
    answers = _answers(client, sid, "What is self attention?")
    assert answers and all(a.startswith("Self-Attention:") for a in answers)
    assert not any("Multi-Head" in a for a in answers)
