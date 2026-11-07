"""An empty (0-byte) paper gets a hint that says so; other unreadable files and valid PDFs are unchanged."""
import pymupdf as fitz

from backend.platform.prereqai_platform import PreReqAIPlatform


def _analyze(tmp_path, data):
    path = tmp_path / "p.pdf"
    path.write_bytes(data)
    return PreReqAIPlatform().analyze(str(path))


def test_an_empty_file_gets_a_specific_hint_and_keeps_the_detail_prefix(tmp_path):
    outcome = _analyze(tmp_path, b"")
    assert outcome["status"] == "failure" and outcome["detail"].startswith("Failed to process the uploaded paper")
    assert "0 bytes" in outcome["hint"] and "report" not in outcome


def test_other_unreadable_files_keep_the_generic_hint(tmp_path):
    outcome = _analyze(tmp_path, b"not a pdf")
    assert outcome["status"] == "failure" and outcome["hint"] == "Upload a text-based PDF research paper."


def test_a_valid_pdf_still_analyses(tmp_path):
    document = fitz.open()
    document.new_page().insert_text((72, 72), "Abstract\nWe study attention.\n1 Introduction\nWe train.\n")
    assert _analyze(tmp_path, document.tobytes())["status"] == "success"
