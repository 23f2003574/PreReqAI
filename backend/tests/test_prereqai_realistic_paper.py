"""A multi-page, two-column paper with equations, a table, references and concepts from every focus area,
run through the real CLI and HTTP upload."""
import json

import pymupdf
from fastapi.testclient import TestClient

from backend.cli import main
from backend.main import app

_BODY = ("The transformer uses multi-head attention and self-attention. Softmax normalizes weights. "
         "A policy gradient agent, a graph neural network and a diffusion model with score matching. ") * 6


def _paper(path, pages=15):
    doc = pymupdf.open()
    for n in range(pages):
        page = doc.new_page()
        top = 72
        if n == 0:
            page.insert_text((72, 60), "Scaling Attention Models for Graph and Diffusion Learning", fontsize=20)
            top = 120
        page.insert_textbox(pymupdf.Rect(72, top, 300, 760), f"{n + 1} Methods\n{_BODY}", fontsize=9)
        page.insert_textbox(pymupdf.Rect(312, top, 540, 760), f"{_BODY}\nSoftmax(x) = exp(x)/sum exp   ({n + 1})", fontsize=9)
    refs = "References\n" + "\n".join(f"[{i}] Author{i}. Title {i}. Venue, 2020." for i in range(1, 40))
    doc.new_page().insert_textbox(pymupdf.Rect(72, 72, 540, 780), refs, fontsize=9)
    doc.save(path)


def test_readiness_covers_every_planned_concept_not_only_those_with_a_resource(tmp_path, capsys):
    path = tmp_path / "paper.pdf"
    _paper(path)
    assert main(["prerequisites", "analyze", str(path), "--json"]) == 0
    report = json.loads(capsys.readouterr().out)["report"]

    plan = [s["concept"] for s in report["learning_plan"]]
    assert len(plan) >= 4 and "Markov Decision Process" in plan  # a planned concept with no curated resource
    assert [p["concept"] for p in report["study_progress"]] == plan
    assert report["readiness"]["total_concepts"] == len(plan)
    assert report["paper"]["title"] == "Scaling Attention Models for Graph and Diffusion Learning"
    assert report["paper"]["pages"] == 16 and report["statistics"]["references"] >= 30

    assert main(["prerequisites", "analyze", str(path), "--json"] + [f for c in plan[:-1] for f in ("--studied", c)]) == 0
    almost = json.loads(capsys.readouterr().out)["report"]["readiness"]
    assert not almost["ready_to_read"] and almost["completed_concepts"] == len(plan) - 1  # one left is not ready


def test_the_http_upload_handles_the_same_paper(tmp_path):
    path = tmp_path / "paper.pdf"
    _paper(path)
    with path.open("rb") as handle:
        response = TestClient(app).post("/api/prerequisites/analyze", files={"paper": ("p.pdf", handle, "application/pdf")})
    body = response.json()
    assert response.status_code == 200 and body["status"] == "success" and body["warnings"] == []
    assert len(body["report"]["study_progress"]) == len(body["report"]["learning_plan"])


def test_numbered_headings_and_hard_wrapped_concept_names_are_understood():
    from backend.concepts.rule_based_concept_detector import RuleBasedConceptDetector
    from backend.models import Paper, Paragraph
    from backend.parsing.scientific_section_parser import SECTION_PATTERN

    text = "1 Introduction\nbody\n2.1 Related Work\nmore\n3. Methods\nx\nAbstract\ny"
    assert [m.group().strip() for m in SECTION_PATTERN.finditer(text)] == ["1 Introduction", "2.1 Related Work", "3. Methods", "Abstract"]

    paper = Paper(source_path="p.pdf", metadata=None)
    paper.paragraphs.append(Paragraph(paragraph_id=1, section_title="x", content="A policy\ngradient and multi-\nhead attention."))
    names = {c.name for c in RuleBasedConceptDetector().detect(paper).concepts}
    assert {"Policy Gradient", "Multi-Head Attention"} <= names
