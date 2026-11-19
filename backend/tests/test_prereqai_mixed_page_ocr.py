"""Pages with a text layer and a scanned image region: the region is recognised and merged in reading order; nothing else costs OCR."""
import pymupdf
import pytest

from backend.concepts.rule_based_concept_detector import RuleBasedConceptDetector
from backend.ingestion import PDFIngestionEngine
from backend.parsing.paragraph_segmenter import ParagraphSegmenter
from backend.parsing.scientific_section_parser import ScientificSectionParser

pytestmark = pytest.mark.prereqai

DIGITAL = "The Transformer is a sequence model that relies on self-attention for every layer. " * 3
SCANNED = "Scaled dot-product attention applies a softmax over the query and key scores to weight the values. " * 2


def image():
    pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 400, 300), False)
    pixmap.set_rect(pixmap.irect, (200, 200, 200))
    return pixmap.tobytes("png")


def make(path, scan_on_top=False, with_image=True, hidden_text=False):
    pdf = pymupdf.open()
    page = pdf.new_page(width=595, height=842)
    text_box, image_box = pymupdf.Rect(60, 60, 540, 300), pymupdf.Rect(80, 420, 520, 740)
    if scan_on_top:
        text_box, image_box = pymupdf.Rect(60, 500, 540, 760), pymupdf.Rect(80, 60, 520, 380)
    page.insert_textbox(text_box, DIGITAL, fontsize=11)
    if with_image:
        page.insert_image(image_box, stream=image())
        if hidden_text:  # a scan that already carries its recognised text layer
            page.insert_textbox(image_box, SCANNED, fontsize=11)
    pdf.save(path)
    return path


class Recorder:
    def __init__(self, text=SCANNED):
        self.calls, self.text = [], text

    def __call__(self, page, box):
        self.calls.append(box)
        return self.text


def ingest(path, region, **budget):
    return PDFIngestionEngine(ocr=lambda page: "", region_ocr=region, **budget).ingest(str(path))


def test_the_scanned_region_is_recognised_merged_after_the_text_and_detected(tmp_path):
    region = Recorder()
    document = ingest(make(tmp_path / "a.pdf"), region)
    page = document.pages[0]
    assert len(region.calls) == 1 and region.calls[0][1] > 400  # only the image region, at its page coordinates
    assert page.ocr and page.ocr_regions == 1 and document.ocr_complete
    assert page.text.index("self-attention") < page.text.index("Scaled dot-product")
    paper = ParagraphSegmenter().segment(ScientificSectionParser().parse(document))
    names = {c.name for c in RuleBasedConceptDetector().detect(paper).concepts}
    assert {"Transformer", "Softmax"} <= names  # one from the digital text, one only from the scan


def test_a_region_above_the_text_is_read_before_it(tmp_path):
    page = ingest(make(tmp_path / "b.pdf", scan_on_top=True), Recorder()).pages[0]
    assert page.text.index("Scaled dot-product") < page.text.index("self-attention")


def test_a_text_only_pdf_never_calls_ocr(tmp_path):
    region = Recorder()
    document = ingest(make(tmp_path / "c.pdf", with_image=False), region)
    assert region.calls == [] and not document.pages[0].ocr


def test_an_image_whose_text_is_already_in_the_page_is_not_recognised_again(tmp_path):
    region = Recorder()
    ingest(make(tmp_path / "d.pdf", hidden_text=True), region)
    assert region.calls == []


def test_recognised_text_already_on_the_page_is_not_added_twice(tmp_path):
    page = ingest(make(tmp_path / "e.pdf"), Recorder(DIGITAL)).pages[0]
    assert page.text.count("relies on self-attention") == DIGITAL.count("relies on self-attention") and page.ocr_regions == 0


def test_the_page_budget_stops_regions_and_the_result_is_reported_partial(tmp_path):
    region = Recorder()
    document = ingest(make(tmp_path / "f.pdf"), region, max_ocr_pages=0)
    page = document.pages[0]
    assert region.calls == [] and page.ocr_stopped and "limit of 0 pages" in page.ocr_error and not document.ocr_complete
    assert "self-attention" in page.text  # the text layer is kept


def test_the_time_budget_stops_regions(tmp_path):
    ticks = iter([0, 99, 99, 99, 99])
    region = Recorder()
    document = PDFIngestionEngine(ocr=lambda p: "", region_ocr=region, max_ocr_seconds=5, clock=lambda: next(ticks)).ingest(str(make(tmp_path / "g.pdf")))
    assert region.calls == [] and not document.ocr_complete


def test_a_recogniser_that_cannot_run_keeps_the_text_layer(tmp_path):
    def broken(page, box):
        raise RuntimeError("no tesseract")

    page = ingest(make(tmp_path / "h.pdf"), broken).pages[0]
    assert "self-attention" in page.text and not page.ocr and page.ocr_error == ""
