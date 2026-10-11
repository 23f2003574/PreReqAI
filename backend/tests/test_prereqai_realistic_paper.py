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


def test_text_before_the_first_heading_is_analysed(tmp_path, capsys):
    path = tmp_path / "paper.pdf"
    doc = pymupdf.open()
    doc.new_page().insert_textbox(
        pymupdf.Rect(72, 72, 540, 760),
        "Diffusion Learning at Scale\nWe study a diffusion model with score matching and a U-Net.\n\n"
        "1 Introduction\nDeep learning has used a transformer.\n\nReferences\n[1] A. Paper.\n", fontsize=10)
    doc.save(path)

    assert main(["prerequisites", "analyze", str(path), "--json"]) == 0
    report = json.loads(capsys.readouterr().out)["report"]
    names = {c["name"] if isinstance(c, dict) else c for c in report["concepts"]}
    assert {"Diffusion Model", "Score Matching", "U-Net", "Transformer"} <= names


def test_arbitrary_numbered_headings_split_sections_but_prose_and_tables_do_not():
    from backend.ingestion import RawDocument
    from backend.ingestion.pdf_ingestion_engine import RawPage
    from backend.parsing.scientific_section_parser import ScientificSectionParser

    text = ("Title\n1 Introduction\nWe begin.\n3 Model Architecture\nThe encoder.\n3.2 Scaled Dot-Product Attention\n"
            "Softmax of scores.\n3 layers were used in the encoder.\n2 0.5 0.7\n4 Training Details\nAdam.\nReferences\n[1] A.\n")
    doc = RawDocument(source_path="p.pdf", metadata=None, pages=[RawPage(page_number=1, text=text)])
    titles = [s.title for s in ScientificSectionParser().parse(doc).sections]
    assert titles == ["Front Matter", "1 Introduction", "3 Model Architecture", "3.2 Scaled Dot-Product Attention",
                      "4 Training Details", "References"]


def test_http_analyze_accepts_studied_concepts_like_the_cli(tmp_path):
    path = tmp_path / "paper.pdf"
    _paper(path)
    client = TestClient(app)

    def analyze(**data):
        with path.open("rb") as handle:
            return client.post("/api/prerequisites/analyze", data=data,
                               files={"paper": ("p.pdf", handle, "application/pdf")}).json()

    plan = [s["concept"] for s in analyze()["report"]["learning_plan"]]
    body = analyze(studied=[plan[0], "Not A Concept"])
    assert [s["concept"] for s in body["report"]["learning_plan"]] == plan  # studied stays in the plan
    assert body["report"]["readiness"]["completed_concepts"] == 1
    assert any("Not A Concept" in w for w in body["warnings"])


def test_author_is_read_from_the_first_page_when_pdf_metadata_is_empty(tmp_path, capsys):
    def make(path, lines):
        doc = pymupdf.open()
        doc.new_page().insert_textbox(pymupdf.Rect(72, 72, 540, 400), "\n".join(lines), fontsize=10)
        doc.save(path)

    def author(path):
        assert main(["prerequisites", "analyze", str(path), "--json"]) == 0
        return json.loads(capsys.readouterr().out)["report"]["paper"]["author"]

    with_names = tmp_path / "a.pdf"
    make(with_names, ["Attention Models", "Ashish Vaswani*, Noam Shazeer and Niki Parmar", "Google Brain",
                      "Abstract", "We study a transformer."])
    assert author(with_names) == "Ashish Vaswani, Noam Shazeer, Niki Parmar"

    without = tmp_path / "b.pdf"
    make(without, ["Attention Models", "Google Brain", "Abstract", "We study a transformer."])
    assert author(without) == "Unknown Author"


def test_a_paper_without_extractable_text_warns_instead_of_claiming_readiness(tmp_path, capsys):
    path = tmp_path / "blank.pdf"
    doc = pymupdf.open()
    doc.new_page()
    doc.save(path)

    assert main(["prerequisites", "analyze", str(path)]) == 0
    assert "no extractable text" in capsys.readouterr().out

    with path.open("rb") as handle:
        body = TestClient(app).post("/api/prerequisites/analyze", files={"paper": ("b.pdf", handle, "application/pdf")}).json()
    assert body["status"] == "success" and any("no extractable text" in w for w in body["warnings"])


def test_a_known_concept_disappears_from_resources_and_missing_prerequisites_too(capsys):
    sample = "examples/prerequisites/sample-paper.pdf"
    assert main(["prerequisites", "analyze", sample, "--json", "--known", "Linear Algebra"]) == 0
    report = json.loads(capsys.readouterr().out)["report"]

    assert "Linear Algebra" not in [s["concept"] for s in report["learning_plan"]]
    assert "Linear Algebra" not in [r["concept"] for r in report["learning_resources"]]
    missing = {m["concept"]: m for m in report["missing_prerequisites"]}
    assert missing["Linear Algebra"]["satisfied"] is True and "known" in missing["Linear Algebra"]["reason"]
    assert missing["Probability"]["satisfied"] is False and report["learning_resources"]  # the rest is untouched
