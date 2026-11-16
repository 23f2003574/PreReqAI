"""Bounded OCR (time and page budget, stopping at page boundaries, partial results) and scan detection for pages with a small text layer.
Only injected recognisers and fake clocks are used: no Tesseract is run."""
from types import SimpleNamespace

import pymupdf
import pytest

from backend.ingestion.pdf_ingestion_engine import PDFIngestionEngine, needs_ocr, read_page
from backend.platform.prereqai_platform import _ocr_warning

pytestmark = pytest.mark.prereqai

STAMP = "Downloaded from the publisher archive by a university library on 12 March 2019"  # 60+ letters: more than a bare page number
BODY = " ".join(["Attention weights are computed from queries and keys over the whole sequence of tokens."] * 4)  # well over 200 letters
FULL = [(0, 0, 600, 800)]


class Page:
    def __init__(self, text="", images=(), blocks=None):
        self.rect, self._text, self._images, self._blocks = SimpleNamespace(width=600, height=800), text, images, blocks

    def get_text(self, kind="text", **kwargs):
        if kind == "dict":
            return {"blocks": []}
        return self._blocks if kind == "blocks" and self._blocks is not None else self._text

    def get_image_info(self):
        return [{"bbox": box} for box in self._images]


def _write_scan_pdf(path, pages):
    """A PDF of `pages` pages, each a full-page image (a scan) with no text layer."""
    document = pymupdf.open()
    pixmap = pymupdf.Pixmap(pymupdf.csGRAY, pymupdf.IRect(0, 0, 60, 80), False)
    pixmap.clear_with(200)
    for _ in range(pages):
        page = document.new_page(width=600, height=800)
        page.insert_image(page.rect, pixmap=pixmap)
    document.save(str(path))
    document.close()
    return path


class Clock:
    """Each reading advances time by `step` seconds, so a recogniser that calls `tick` is 'slow'."""

    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def test_a_slow_recogniser_reaches_the_deadline_and_stops_further_pages(tmp_path):
    clock, recognised = Clock(), []

    def slow(page):
        recognised.append(page)
        clock.now += 40  # each page takes 40 s
        return "recognised words"

    document = PDFIngestionEngine(ocr=slow, max_ocr_seconds=100, clock=clock).ingest(str(_write_scan_pdf(tmp_path / "s.pdf", 6)))
    assert len(recognised) == 3  # 0, 40 and 80 s are inside the budget; at 120 s the next page is not started
    assert [p.ocr for p in document.pages] == [True, True, True, False, False, False]
    assert [p.ocr_stopped for p in document.pages] == [False, False, False, True, True, True]
    assert not document.ocr_complete and "100 seconds" in document.pages[3].ocr_error


def test_text_read_before_the_deadline_survives_and_is_not_repeated(tmp_path):
    clock = Clock()

    def slow(page):
        clock.now += 60
        return "first page words"

    document = PDFIngestionEngine(ocr=slow, max_ocr_seconds=50, clock=clock).ingest(str(_write_scan_pdf(tmp_path / "s.pdf", 3)))
    assert document.pages[0].text == "first page words" and document.pages[0].ocr
    assert document.full_text.count("first page words") == 1  # the stopped pages add nothing and nothing was recognised twice
    assert [p.page_number for p in document.pages] == [1, 2, 3]


def test_a_page_limit_stops_at_a_page_boundary(tmp_path):
    seen = []
    document = PDFIngestionEngine(ocr=lambda p: seen.append(1) or "words", max_ocr_pages=2).ingest(str(_write_scan_pdf(tmp_path / "s.pdf", 4)))
    assert len(seen) == 2 and [p.ocr_stopped for p in document.pages] == [False, False, True, True]
    assert "2 pages" in document.pages[2].ocr_error


def test_a_complete_document_is_distinguished_from_a_partial_one(tmp_path):
    complete = PDFIngestionEngine(ocr=lambda p: "words", max_ocr_pages=5).ingest(str(_write_scan_pdf(tmp_path / "s.pdf", 2)))
    assert complete.ocr_complete and _ocr_warning(SimpleNamespace(pages=complete.pages)) != []
    assert not any("partial" in note for note in _ocr_warning(SimpleNamespace(pages=complete.pages)))


def test_a_partial_document_returns_an_explicit_warning(tmp_path):
    document = PDFIngestionEngine(ocr=lambda p: "words", max_ocr_pages=1).ingest(str(_write_scan_pdf(tmp_path / "s.pdf", 3)))
    notes = _ocr_warning(SimpleNamespace(pages=document.pages))
    partial = next(note for note in notes if "partial" in note)
    assert "pages 2, 3" in partial and "OCR limit of 1 pages" in partial
    assert not any("could not be read" in note for note in notes)  # a budget stop is not reported as a failure to read


def test_no_budget_means_no_limit_and_failures_keep_the_text_layer(tmp_path):
    document = PDFIngestionEngine(ocr=lambda p: "words").ingest(str(_write_scan_pdf(tmp_path / "s.pdf", 3)))
    assert document.ocr_complete and all(p.ocr for p in document.pages)

    def broken(page):
        raise RuntimeError("no Tesseract")

    page = read_page(Page(BODY, FULL), 1, broken)
    assert page.text.startswith("Attention weights") and not page.ocr and page.ocr_error == ""  # a usable text layer is never replaced


def test_a_digital_page_is_not_sent_to_ocr():
    calls = []
    page = read_page(Page(BODY, []), 1, lambda p: calls.append(p) or "x", stop=lambda: "stop")
    assert page.text.startswith("Attention weights") and calls == [] and not page.ocr_stopped


def test_a_scan_with_only_a_small_text_layer_stamp_needs_ocr():
    stamp_blocks = [(20, 770, 500, 785, STAMP, 0, 0)]
    assert needs_ocr(Page(STAMP, FULL, blocks=stamp_blocks), STAMP)
    page = read_page(Page(STAMP, FULL, blocks=stamp_blocks), 1, lambda p: "the real page text")
    assert page.ocr and page.text == "the real page text"


def test_a_usable_text_layer_does_not_trigger_ocr_even_over_a_page_image():
    blocks = [(50, 60, 550, 700, BODY, 0, 0)]
    assert not needs_ocr(Page(BODY, FULL, blocks=blocks), BODY)  # plenty of text: an OCR'd scan or a page with a background
    middle = [(50, 300, 550, 340, STAMP, 0, 0)]
    assert not needs_ocr(Page(STAMP, FULL, blocks=middle + [(50, 100, 550, 700, "x", 0, 0)]), STAMP)  # short text spread over the page
    assert not needs_ocr(Page(STAMP, [(0, 0, 300, 300)], blocks=[(20, 770, 500, 785, STAMP, 0, 0)]), STAMP)  # a figure, not the page
    assert not needs_ocr(Page(STAMP, FULL), STAMP)  # no block geometry: keep the short text layer


def test_the_pipeline_passes_its_ocr_budget_to_ingestion_and_returns_the_partial_paper(tmp_path):
    from time import sleep

    from backend.pipeline import ResearchPaperPipeline

    def slow(page):
        sleep(0.3)
        return "Attention is computed with softmax over queries and keys."

    pipeline = ResearchPaperPipeline()
    pipeline.ingestion = PDFIngestionEngine(ocr=slow)
    result = pipeline.run(str(_write_scan_pdf(tmp_path / "s.pdf", 3)), ocr_seconds=0.2)
    assert [(p.ocr, p.ocr_stopped) for p in result.paper.pages] == [(True, False), (False, True), (False, True)]
    assert any("partial" in note for note in _ocr_warning(result.paper))
