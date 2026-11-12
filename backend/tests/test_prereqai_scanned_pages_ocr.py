"""Scanned pages: detection, OCR fallback through an injectable recogniser, mixed documents, failures, and the warnings."""
from types import SimpleNamespace

import pytest

from backend.ingestion.pdf_ingestion_engine import default_ocr, needs_ocr, read_page
from backend.platform.prereqai_platform import _ocr_warning

pytestmark = pytest.mark.prereqai

TEXT = "Attention is all you need for sequence transduction models."


class Page:
    """Just enough of a PyMuPDF page: size, text layer and image boxes."""

    def __init__(self, text="", images=(), width=600, height=800):
        self.rect, self._text, self._images = SimpleNamespace(width=width, height=height), text, images

    def get_text(self, kind="text", **kwargs):
        return {"blocks": []} if kind == "dict" else self._text

    def get_image_info(self):
        return [{"bbox": box} for box in self._images]


FULL_PAGE = [(0, 0, 600, 800)]
LOGO = [(0, 0, 50, 50)]


def test_a_text_page_is_never_sent_to_ocr_even_with_a_full_page_image():
    calls = []
    page = read_page(Page(TEXT, FULL_PAGE), 1, lambda p: calls.append(p) or "x")
    assert (page.text, page.ocr, page.ocr_error, calls) == (TEXT, False, "", [])


def test_blank_pages_and_pages_with_only_a_small_image_are_not_scans():
    assert not needs_ocr(Page(""), "") and not needs_ocr(Page("", LOGO), "")
    assert not needs_ocr(Page("", FULL_PAGE, width=0), "")


def test_a_scanned_page_uses_the_ocr_text_in_the_ingestion_format():
    page = read_page(Page("  ", FULL_PAGE), 3, lambda p: "  Policy ﬁrst gradient  ")
    assert page.page_number == 3 and page.ocr and page.text == "Policy first gradient" and page.ocr_error == ""


def test_a_mixed_document_keeps_page_order_and_boundaries():
    pages = [Page(TEXT), Page("", FULL_PAGE), Page(""), Page(TEXT, FULL_PAGE), Page("", FULL_PAGE)]
    read = [read_page(p, n, lambda p: "scanned words") for n, p in enumerate(pages, start=1)]
    assert [(r.page_number, r.ocr, r.text) for r in read] == [
        (1, False, TEXT), (2, True, "scanned words"), (3, False, ""), (4, False, TEXT), (5, True, "scanned words")]


def test_ocr_that_cannot_run_is_reported_not_hidden():
    def broken(page):
        raise RuntimeError("Tesseract is not installed")

    page = read_page(Page("", FULL_PAGE), 2, broken)
    assert page.text == "" and not page.ocr and "OCR could not run: Tesseract is not installed" in page.ocr_error


def test_ocr_that_finds_nothing_is_reported():
    page = read_page(Page("", FULL_PAGE), 2, lambda p: "   ")
    assert not page.ocr and "no text" in page.ocr_error


def test_default_ocr_turns_any_engine_failure_into_a_runtime_error():
    class Failing(Page):
        def get_textpage_ocr(self, **kwargs):
            raise OSError("no tesseract")

    with pytest.raises(RuntimeError):
        default_ocr(Failing("", FULL_PAGE))


def _paper(*pages):
    return SimpleNamespace(pages=list(pages))


def test_warnings_name_the_ocr_pages_and_the_unreadable_pages():
    pages = [read_page(Page("", FULL_PAGE), 1, lambda p: "words"), read_page(Page(TEXT), 2, None), read_page(Page("", FULL_PAGE), 3, lambda p: "")]
    warnings = _ocr_warning(_paper(*pages))
    assert len(warnings) == 2 and "Pages 1 are scans" in warnings[0] and "Scanned pages 3 could not be read" in warnings[1]


def test_text_only_documents_add_no_ocr_warning():
    assert _ocr_warning(_paper(read_page(Page(TEXT), 1, None))) == [] and _ocr_warning(_paper()) == []
