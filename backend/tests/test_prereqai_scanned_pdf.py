"""A scanned paper (pages that are only a picture of text) has no extractable text: the analysis must say so, not look like a
finished analysis of an empty paper. A text-based PDF is unaffected."""
import pymupdf
import pytest

from backend.platform import PreReqAIPlatform

pytestmark = pytest.mark.prereqai

WARNING = "no extractable text"


def _scanned(path):
    source = pymupdf.open()
    source.new_page().insert_text((72, 72), "Attention softmax gradient descent", fontsize=20)
    picture = source[0].get_pixmap(dpi=72).tobytes("png")  # the page as a raster image, as a scanner produces it
    document = pymupdf.open()
    document.new_page().insert_image(document[0].rect, stream=picture)
    document.save(path)


def test_an_image_only_pdf_is_reported_as_having_no_extractable_text(tmp_path):
    path = tmp_path / "scan.pdf"
    _scanned(path)
    outcome = PreReqAIPlatform().analyze(str(path))
    assert outcome["report"]["concepts"] == []
    assert any(WARNING in warning and "OCR" in warning for warning in outcome["warnings"]), outcome["warnings"]


def test_a_text_based_pdf_gets_no_such_warning(tmp_path):
    path = tmp_path / "text.pdf"
    document = pymupdf.open()
    document.new_page().insert_text((72, 72), "Abstract\nWe study softmax and gradient descent.", fontsize=11)
    document.save(path)
    outcome = PreReqAIPlatform().analyze(str(path))
    assert outcome["status"] == "success" and outcome["report"]["concepts"]
    assert not any(WARNING in warning for warning in outcome["warnings"])
