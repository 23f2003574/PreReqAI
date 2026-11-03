"""Pipeline integration (PDF ingestion -> sections -> concept detection -> session -> tutor): the sections the tutor
cites as covering a concept agree with the detector, which ignores the reference list."""
from pathlib import Path

import pymupdf
import pytest
from fastapi.testclient import TestClient

from backend.main import app

pytestmark = pytest.mark.prereqai


def _paper(path: Path) -> Path:
    document = pymupdf.open()
    page = document.new_page()
    lines = ["Learning Rate Schedules for Vision", "Abstract", "We study the use of gradient descent.",
             "1 Introduction", "Gradient descent is common.", "References",
             "[1] Smith. A survey of gradient descent methods. 2015."]
    for number, line in enumerate(lines):
        page.insert_text((40, 40 + 16 * number), line)
    document.save(str(path))
    return path


def test_a_cited_title_in_the_references_is_not_cited_back_as_supporting_a_concept(tmp_path):
    client = TestClient(app)
    with _paper(tmp_path / "paper.pdf").open("rb") as handle:
        session = client.post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")}).json()

    answer = client.post(f"/api/session/{session['session_id']}/question",
                         json={"question": "What does Gradient Descent need?"}).json()["responses"][0]

    assert answer["supporting_concepts"] == ["Gradient Descent"]
    assert answer["supporting_sections"] == ["Abstract", "1 Introduction"]
    assert [c["occurrences"] for c in session["report"]["concept_evidence"]] == [2]  # the detector agrees: 2 body mentions
