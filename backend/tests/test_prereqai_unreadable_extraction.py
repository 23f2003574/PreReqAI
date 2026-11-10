import pymupdf
import pytest

from backend.platform.prereqai_platform import PreReqAIPlatform

pytestmark = pytest.mark.prereqai


def _warnings(tmp_path, text):
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), text)
    path = tmp_path / "p.pdf"
    doc.save(path)
    outcome = PreReqAIPlatform().analyze(str(path))
    assert outcome["status"] == "success"
    return " ".join(outcome["warnings"])


def test_font_placeholder_text_is_reported_as_unreadable(tmp_path):
    assert "unreadable" in _warnings(tmp_path, "(cid:12)(cid:45) (cid:77)(cid:9)")
    assert "unreadable" in _warnings(tmp_path, "��� ��")


def test_whitespace_only_pdf_keeps_the_no_extractable_text_warning(tmp_path):
    warning = _warnings(tmp_path, "   ")
    assert "no extractable text" in warning and "unreadable" not in warning


def test_readable_text_gets_neither_warning(tmp_path):
    warning = _warnings(tmp_path, "Attention is computed with softmax over the scores.")
    assert "unreadable" not in warning and "no extractable text" not in warning
