"""A realistic typeset paper (two-line title, author line, IEEE-style roman headings, unnumbered subsections, a bibliography) goes through
analysis, the plan export and a question with the right title, sections, references and concepts."""
import pymupdf
import pytest
from starlette.testclient import TestClient

from backend.main import app

BODY = [
    ("Denoising Diffusion Probabilistic", 20), ("Models for Image Synthesis", 20), ("Jonathan Ho, Ajay Jain", 11),
    ("Abstract", 11), ("We train a diffusion model with a score matching objective.", 10),
    ("I. INTRODUCTION", 12), ("Diffusion models use a reverse process and gradient descent.", 10),
    ("II. METHOD", 12), ("The loss is minimised with gradient descent over a neural network.", 10),
    ("Implementation Details", 12), ("We use Adam and backpropagation.", 10),
]
CITED = [("[1] A. Author. Convolutional neural network surveys. 2019.", 9), ("[2] B. Author. Generative adversarial network advances. 2020.", 9)]


def _pdf(tmp_path, bibliography_heading):
    path = tmp_path / "paper.pdf"
    doc = pymupdf.open()
    page, y = doc.new_page(), 72
    for text, size in [*BODY, (bibliography_heading, 12), *CITED]:
        page.insert_text((72, y), text, fontsize=size)
        y += size + 6
    doc.save(path)
    return path.read_bytes()


@pytest.mark.parametrize("heading", ["REFERENCES", "VII. REFERENCES"])
def test_typeset_paper_is_read_as_a_whole(tmp_path, heading):
    client = TestClient(app)
    body = client.post("/api/prerequisites/analyze", files={"paper": ("paper.pdf", _pdf(tmp_path, heading), "application/pdf")}).json()
    report = body["report"]

    assert report["paper"]["title"] == "Denoising Diffusion Probabilistic Models for Image Synthesis"
    assert report["paper"]["author"] == "Jonathan Ho, Ajay Jain"
    assert report["statistics"]["references"] == 2
    assert report["concepts"] == ["Gradient Descent", "Backpropagation", "Diffusion Model", "Reverse Process", "Score Matching"]  # cited titles add none
    assert [step["concept"] for step in report["learning_plan"]] == ["Linear Algebra", "Probability", "Calculus", "Neural Networks"]

    sid = body["session_id"]
    plan = client.get(f"/api/session/{sid}/plan").text
    assert plan.startswith("# Study plan: Denoising Diffusion Probabilistic Models for Image Synthesis\n")
    answer = client.post(f"/api/session/{sid}/question", json={"question": "How long will calculus take?"}).json()["responses"][0]["answer"]
    assert answer == "Calculus: about 10 hours of study."
