"""OCR with the real Tesseract engine: a scanned page, rotated scans, a noisy scan, a scanned region beside a text layer, the OCR budget and language data.

These are the only tests that run the engine; every other OCR test uses a stand-in recogniser and proves the logic around it, not the engine. They are skipped when the tesseract binary
or its English data is missing (the skip names the reason), and FAIL instead when PREREQAI_REQUIRE_TESSERACT=1, which the CI `ocr` job sets so that it cannot pass by skipping.
Texts are large and clear, and the assertions look for a few distinctive words, not exact output, because recognition is probabilistic."""
import os
import random

import pymupdf
import pytest

from backend.concepts.rule_based_concept_detector import RuleBasedConceptDetector
from backend.ingestion import PDFIngestionEngine
from backend.ingestion.pdf_ingestion_engine import ocr_languages
from backend.models import Paper
from backend.parsing.paragraph_segmenter import ParagraphSegmenter
from backend.parsing.scientific_section_parser import ScientificSectionParser
from backend.platform.prereqai_platform import _ocr_warning

pytestmark = pytest.mark.tesseract
TEXT = ("The Transformer relies on self-attention. A softmax over the scores weights the values. "
        "Gradient descent trains the network with backpropagation.")


def engine_problem():
    try:
        tessdata = pymupdf.get_tessdata()
    except Exception as error:  # PyMuPDF raises RuntimeError when Tesseract is not installed
        return f"the tesseract engine was not found ({error})"
    return "" if os.path.exists(os.path.join(str(tessdata), "eng.traineddata")) else f"English language data (eng.traineddata) is missing from {tessdata}"


@pytest.fixture(scope="module", autouse=True)
def real_engine():
    problem = engine_problem()
    if problem and os.environ.get("PREREQAI_REQUIRE_TESSERACT") == "1":
        pytest.fail(f"PREREQAI_REQUIRE_TESSERACT=1 but {problem}")
    if problem:
        pytest.skip(f"{problem}; the CI `ocr` job provisions it, and without it these real-engine tests do not run")


def text_pixmap(text=TEXT, width=1200, height=700, size=34):
    page = pymupdf.open().new_page(width=width, height=height)
    page.insert_textbox(pymupdf.Rect(40, 40, width - 40, height - 40), text, fontsize=size, fontname="helv")
    return page.get_pixmap(dpi=150)


def scan(path, pixmap, text_layer=None):
    """A one-page PDF whose page is the picture (a 'scan'), optionally with a short real text layer above it."""
    pdf = pymupdf.open()
    page = pdf.new_page(width=pixmap.width * 72 / 150, height=pixmap.height * 72 / 150)
    page.insert_image(page.rect, pixmap=pixmap)
    if text_layer:
        page.insert_textbox(pymupdf.Rect(20, 10, page.rect.width - 20, 60), text_layer, fontsize=11)
    pdf.save(str(path))
    return str(path)


def rotated(pixmap, degrees):
    from PIL import Image

    image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples).rotate(-degrees, expand=True)  # clockwise
    out = pymupdf.Pixmap(pymupdf.csRGB, image.width, image.height, image.tobytes(), False)
    return out


def words(page):
    return " ".join(page.text.lower().split())


def test_a_scanned_page_is_recognised_and_its_concepts_are_detected(tmp_path):
    document = PDFIngestionEngine().ingest(scan(tmp_path / "a.pdf", text_pixmap()))
    page = document.pages[0]
    assert page.ocr and page.ocr_error == "" and page.ocr_rotation == 0 and page.ocr_quality >= 0.6
    assert "transformer" in words(page) and "softmax" in words(page)
    paper = ParagraphSegmenter().segment(ScientificSectionParser().parse(document))
    assert {"Transformer", "Softmax"} <= {c.name for c in RuleBasedConceptDetector().detect(paper).concepts}
    assert any("scans" in note for note in _ocr_warning(Paper(source_path="x", metadata=None, pages=document.pages)))  # the learner is told these words came from OCR


@pytest.mark.parametrize("degrees", [180, 90, 270])
def test_a_rotated_scan_is_turned_upright_and_read(tmp_path, degrees):
    document = PDFIngestionEngine().ingest(scan(tmp_path / f"r{degrees}.pdf", rotated(text_pixmap(), degrees)))
    page = document.pages[0]
    assert page.ocr and page.ocr_rotation == (360 - degrees) % 360 and "transformer" in words(page), (page.ocr_rotation, words(page)[:80])  # turned back by the complementary angle


def test_a_noisy_scan_is_not_trusted_and_adds_no_concepts(tmp_path):
    random.seed(7)
    noise = pymupdf.Pixmap(pymupdf.csRGB, 1000, 600, bytes(random.randrange(256) for _ in range(1000 * 600 * 3)), False)
    document = PDFIngestionEngine().ingest(scan(tmp_path / "n.pdf", noise))
    page = document.pages[0]
    assert not page.ocr and page.text.strip() == "" and page.ocr_error  # nothing recognisable: no text, and the reason is recorded
    paper = ParagraphSegmenter().segment(ScientificSectionParser().parse(document))
    assert RuleBasedConceptDetector().detect(paper).concepts == []


def test_a_scanned_region_beside_a_text_layer_is_recognised_and_ordered_after_it(tmp_path):
    pdf = pymupdf.open()
    page = pdf.new_page(width=595, height=842)
    page.insert_textbox(pymupdf.Rect(60, 50, 540, 200), "The experiments use gradient descent with the Adam optimizer on every dataset considered here. " * 2, fontsize=11)
    page.insert_image(pymupdf.Rect(60, 400, 540, 700), pixmap=text_pixmap("The Transformer relies on self-attention and a softmax over the scores.", 1000, 520, 38))
    pdf.save(str(tmp_path / "m.pdf"))
    document = PDFIngestionEngine().ingest(str(tmp_path / "m.pdf"))
    page = document.pages[0]
    assert page.ocr_regions >= 1 and "adam optimizer" in words(page) and "transformer" in words(page) and words(page).index("adam optimizer") < words(page).index("transformer")


def test_the_ocr_page_budget_stops_the_real_engine_and_the_result_is_marked_partial(tmp_path):
    document = PDFIngestionEngine(max_ocr_pages=0).ingest(scan(tmp_path / "b.pdf", text_pixmap()))
    assert not document.ocr_complete and document.pages[0].ocr_stopped and "limit of 0 pages" in document.pages[0].ocr_error


def test_english_is_the_default_and_a_missing_language_pack_is_reported_not_replaced_by_english(tmp_path, monkeypatch):
    assert ocr_languages() == ["eng"]
    path = scan(tmp_path / "l.pdf", text_pixmap())
    monkeypatch.setenv("PREREQAI_OCR_LANGS", "eng")
    assert "transformer" in words(PDFIngestionEngine().ingest(path).pages[0])
    missing = "zzz"  # a well-formed code no one installs
    monkeypatch.setenv("PREREQAI_OCR_LANGS", f"eng,{missing}")
    page = PDFIngestionEngine().ingest(path).pages[0]
    assert not page.ocr and missing in page.ocr_error and "not installed" in page.ocr_error  # never silently read in English instead
