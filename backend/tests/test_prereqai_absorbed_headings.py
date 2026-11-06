"""An unnumbered heading outside the recognised list is folded into the previous section. The parser's output is unchanged, but the
analysis now warns, through the existing `warnings` list (platform result, CLI output and HTTP response)."""
import pymupdf as fitz
import pytest
from starlette.testclient import TestClient

from backend.cli import main as cli_main
from backend.main import app
from backend.parsing.scientific_section_parser import ScientificSectionParser
from backend.platform import PreReqAIPlatform

pytestmark = pytest.mark.prereqai

TEXT = (
    "A Paper\n\nAbstract\nWe study sorting.\n\n1 Introduction\nWe sort lists quickly.\n\n"
    "Sorting Strategy\nWe use softmax weights.\n\n2 Method\nWe sort.\n"
)
CLEAN = "A Paper\n\nAbstract\nWe study sorting.\n\n1 Introduction\nWe sort lists quickly\nand then stop.\n\n2 Method\nWe sort.\n"
MARKER = "Possible section headings were not recognised"


def _pdf(tmp_path, text):
    document = fitz.open()
    document.new_page().insert_text((72, 72), text, fontsize=11)
    path = tmp_path / "paper.pdf"
    path.write_bytes(document.tobytes())
    return path


def test_the_heading_is_still_absorbed_and_the_platform_warns(tmp_path):
    path = _pdf(tmp_path, TEXT)
    outcome = PreReqAIPlatform().analyze(str(path))
    assert outcome["status"] == "success", outcome
    assert any(MARKER in w and "'Sorting Strategy' (inside '1 Introduction')" in w for w in outcome["warnings"]), outcome["warnings"]


def test_section_extraction_is_unchanged(tmp_path):
    from backend.ingestion import PDFIngestionEngine

    paper = ScientificSectionParser().parse(PDFIngestionEngine().ingest(str(_pdf(tmp_path, TEXT))))
    titles = [section.title for section in paper.sections]
    assert titles == ["Front Matter", "Abstract", "1 Introduction", "2 Method"]
    assert "Sorting Strategy" in paper.sections[2].content


def test_wrapped_lines_and_recognised_headings_do_not_warn(tmp_path):
    outcome = PreReqAIPlatform().analyze(str(_pdf(tmp_path, CLEAN)))
    assert outcome["status"] == "success", outcome
    assert not any(MARKER in w for w in outcome["warnings"])


def test_the_warning_reaches_the_http_response(tmp_path):
    path = _pdf(tmp_path, TEXT)
    with open(path, "rb") as handle:
        body = TestClient(app).post("/api/prerequisites/analyze", files={"paper": ("paper.pdf", handle, "application/pdf")}).json()
    assert any(MARKER in w for w in body["warnings"]), body["warnings"]


def test_the_warning_reaches_the_cli_output(tmp_path, capsys):
    cli_main(["prerequisites", "analyze", str(_pdf(tmp_path, TEXT)), "--json"])
    assert MARKER in capsys.readouterr().out
