"""Terms a paper defines that the registry does not know are reported as not analysed, not silently dropped."""
import json
from types import SimpleNamespace

import pymupdf
import pytest

from backend.cli import main
from backend.models import Paper
from backend.reporting.learning_report_generator import LearningReportGenerator

pytestmark = pytest.mark.prereqai

DEFINED = "Graph Isomorphism Network (GIN) and Dynamic Time Warping (DTW) are used. A transformer uses attention."


def make_pdf(path, text):
    pdf = pymupdf.open()
    pdf.new_page().insert_textbox(pymupdf.Rect(50, 50, 550, 780), text)
    pdf.save(path)


def report_for(terms):
    paper = SimpleNamespace(unrecognised_terms=terms)
    return LearningReportGenerator._not_analysed(paper)


def test_terms_are_deduplicated_ignoring_case_and_keep_first_appearance_order():
    assert report_for(["A B (AB)", "C D (CD)", "a b (ab)", "A B (AB)"]) == ["A B (AB)", "C D (CD)"]


def test_no_terms_means_an_empty_list_and_no_note():
    assert report_for([]) == [] and report_for(None) == []


def test_the_terms_reach_the_report_with_an_explanation(tmp_path):
    from backend.platform import platform

    pdf = tmp_path / "p.pdf"
    make_pdf(str(pdf), DEFINED)
    report = platform.analyze(str(pdf))["report"]
    assert report["not_analysed_terms"] == ["Graph Isomorphism Network (GIN)", "Dynamic Time Warping (DTW)"]
    assert report["not_analysed_total"] == 2 and "does not support" in report["not_analysed_note"]


def test_limit_applies(monkeypatch):
    monkeypatch.setattr(LearningReportGenerator, "NOT_ANALYSED_LIMIT", 1)
    # one term is shown and the total still counts both
    paper = Paper(source_path="p.pdf", metadata=SimpleNamespace(title="t", author="a", subject="", keywords="", creator="", producer="", page_count=1))
    paper.unrecognised_terms = ["A B (AB)", "C D (CD)"]
    report = LearningReportGenerator().generate(paper)
    assert report["not_analysed_terms"] == ["A B (AB)"] and report["not_analysed_total"] == 2


def test_a_paper_without_such_terms_has_an_empty_field(tmp_path, capsys):
    pdf = tmp_path / "p.pdf"
    make_pdf(str(pdf), "A transformer uses attention. Attention again.")
    assert main(["prerequisites", "analyze", str(pdf), "--json"]) == 0
    report = json.loads(capsys.readouterr().out)["report"]
    assert report["not_analysed_terms"] == [] and report["not_analysed_total"] == 0 and report["not_analysed_note"] == ""
    assert main(["prerequisites", "analyze", str(pdf)]) == 0 and "not analysed" not in capsys.readouterr().out


def test_cli_summary_names_the_terms(tmp_path, capsys):
    pdf = tmp_path / "p.pdf"
    make_pdf(str(pdf), DEFINED)
    assert main(["prerequisites", "analyze", str(pdf)]) == 0
    out = capsys.readouterr().out
    assert "not analysed" in out and "Graph Isomorphism Network (GIN)" in out and "no prerequisites" in out


def test_the_concept_results_are_unchanged_by_the_new_fields(tmp_path, capsys):
    pdf = tmp_path / "p.pdf"
    make_pdf(str(pdf), DEFINED)
    assert main(["prerequisites", "analyze", str(pdf), "--json"]) == 0
    report = json.loads(capsys.readouterr().out)["report"]
    assert sorted(report["concepts"]) == ["Attention", "Transformer"]


def test_the_web_page_renders_the_field():
    from pathlib import Path

    page = (Path(__file__).resolve().parents[1] / "web" / "index.html").read_text(encoding="utf-8")
    assert "not_analysed_terms" in page and "not_analysed_note" in page and "Terms not analysed" in page
