"""PDF mode of the evaluation harness: fixtures, real-pipeline ingestion, scoring, determinism and the command line."""
import json
import sys
from types import SimpleNamespace

import pymupdf
import pytest

from backend.concepts import ConceptRegistry
from backend.ingestion import PDFIngestionEngine
from backend.models import Paper, Paragraph, Prerequisite
from backend.prereqai_eval import __main__ as cli
from backend.prereqai_eval import pdf_eval
from backend.prereqai_eval.harness import evaluate
from backend.prerequisites.missing_prerequisite_analyzer import MissingPrerequisiteAnalyzer, section_role
from backend.prerequisites.prerequisite_detector import PrerequisiteDetector
from backend.prereqai_eval.pdf_fixtures import FIXTURES, write_fixture_pdfs

pytestmark = pytest.mark.prereqai


def _text(path):
    with pymupdf.open(path) as pdf:
        return [page.get_text("text") for page in pdf]


def test_fixtures_are_structurally_distinct_and_annotated_consistently():
    assert len(FIXTURES) >= 3 and len({f["id"] for f in FIXTURES}) == len(FIXTURES)
    assert {f["columns"] for f in FIXTURES} == {1, 2}
    assert any(not title[0].isdigit() and title.split()[0] != "I." for f in FIXTURES for title, _ in f["sections"])
    registry = {c.name for c in ConceptRegistry().all()}
    subjects = {p for targets in PrerequisiteDetector.PREREQUISITE_RULES.values() for p in targets}
    for fixture in FIXTURES:
        assert set(fixture["concepts"]) <= registry and set(fixture["covered"]) <= subjects | registry
        assert all(section_role(title) == role for title, role in fixture["sections"]), fixture["id"]  # annotations follow the written policy


def test_pdfs_are_generated_reproducibly_with_running_header_and_page_numbers(tmp_path):
    first, second = write_fixture_pdfs(tmp_path / "a"), write_fixture_pdfs(tmp_path / "b")
    for fixture in FIXTURES:
        pages = _text(first[fixture["id"]])
        assert pages == _text(second[fixture["id"]]) and len(pages) >= 3
        assert all(fixture["header"] in page and f"Page {n}" in page for n, page in enumerate(pages, start=1))


def test_real_ingestion_removes_the_noise_and_reads_both_columns(tmp_path):
    paths = write_fixture_pdfs(tmp_path)
    for fixture in FIXTURES:
        document = PDFIngestionEngine().ingest(str(paths[fixture["id"]]))
        assert sum(page.removed_lines for page in document.pages) > 0
        assert fixture["header"] not in document.full_text.replace(fixture["blocks"][0][1], "", 1)
    text = PDFIngestionEngine().ingest(str(paths["ieee-2col"])).full_text
    assert text.index("II. BACKGROUND") < text.index("III. PROPOSED METHOD") < text.index("IV. EXPERIMENTS")


def test_evaluation_runs_the_full_pipeline_and_is_deterministic():
    first = pdf_eval.evaluate_pdf()
    assert first == pdf_eval.evaluate_pdf()
    assert first["synthetic"] and first["pipeline"] == {"succeeded": len(FIXTURES), "total": len(FIXTURES)}
    for row in first["fixtures"]:
        assert row["ok"] and row["concepts"]["tp"] > 0 and row["headings"]["tp"] > 0  # sections and concepts came from the PDF, not from the annotations
    for key in ("headings", "concepts", "coverage"):
        assert 0.0 <= first[key]["precision"] <= 1.0 and 0.0 <= first[key]["recall"] <= 1.0


def _coverage_row(section):
    paper = Paper(source_path="x.pdf", metadata=None)
    paper.paragraphs = [Paragraph(1, "1 Introduction", "We begin."),
                        Paragraph(2, section, "A random variable, conditional probability and Bayes rule are used. " * 2)]
    paper.prerequisites = [Prerequisite(concept="Probability", reason="r", confidence=1.0)]
    paper.concepts = []
    MissingPrerequisiteAnalyzer().analyze(paper)
    paper.sections = []
    fixture = {"sections": [], "concepts": [], "covered": ["Probability"]}
    return pdf_eval.score_fixture(fixture, paper)["coverage"]


def test_wrong_section_attribution_changes_the_coverage_metrics():
    taught, absorbed = _coverage_row("2 Background"), _coverage_row("4 Experiments")  # the same text, filed under a different section
    assert taught["recall"] == 1.0 and absorbed["recall"] == 0.0 and absorbed["fn"] == 1


def test_scoring_reports_missed_and_spurious_headings_and_wrong_roles():
    fixture = {"sections": [("Background", "instructional"), ("Experiments", "other")], "concepts": ["Softmax"], "covered": []}
    sections = [SimpleNamespace(title="2 Background"), SimpleNamespace(title="3 Method"), SimpleNamespace(title="Front Matter")]
    paper = SimpleNamespace(sections=sections, concepts=[SimpleNamespace(name="Softmax")], missing_prerequisites=[])
    result = pdf_eval.score_fixture(fixture, paper)
    assert result["headings"]["missed"] == ["experiments"] and result["headings"]["spurious"] == ["method"]
    assert result["roles"] == {"correct": 1, "total": 2, "wrong": [], "accuracy": 0.5}
    assert result["concepts"]["f1"] == 1.0
    paper.sections = [SimpleNamespace(title="2 Background"), SimpleNamespace(title="3 Method")]
    fixture["sections"] = [("Background", "other")]
    assert pdf_eval.score_fixture(fixture, paper)["roles"]["wrong"] == ["background"]


def test_cli_pdf_mode_text_and_json(capsys):
    assert cli.main(["--pdf"]) == 0
    out = capsys.readouterr().out
    assert "SYNTHETIC" in out and "not validation on real published papers" in out and "PIPELINE" in out
    assert cli.main(["--pdf", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["mode"] == "pdf"


def test_cli_without_pdf_is_the_unchanged_text_mode(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "MICRO" in out and "SYNTHETIC" not in out
    assert evaluate()["concepts"]["f1"] > 0


def test_cli_rejects_pdf_with_fixtures_and_reports_a_missing_library(capsys, monkeypatch):
    assert cli.main(["--pdf", "--fixtures", "other.json"]) == 2
    assert "cannot be combined" in capsys.readouterr().err
    monkeypatch.setitem(sys.modules, "pymupdf", None)  # import pymupdf now raises ImportError
    assert cli.main(["--pdf"]) == 2
    assert "pip install -r requirements.txt" in capsys.readouterr().err
