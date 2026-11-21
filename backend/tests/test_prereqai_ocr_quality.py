"""OCR quality gate, rotation recovery, configured languages and their warnings (Tesseract and its language packs are mocked)."""
import pymupdf
import pytest

from backend.concepts.rule_based_concept_detector import RuleBasedConceptDetector
from backend.ingestion import PDFIngestionEngine
from backend.ingestion.pdf_ingestion_engine import (OcrLanguageError, default_ocr, ocr_language_argument, ocr_languages, ocr_quality)
from backend.parsing.paragraph_segmenter import ParagraphSegmenter
from backend.parsing.scientific_section_parser import ScientificSectionParser
from backend.platform.prereqai_platform import _ocr_warning

pytestmark = pytest.mark.prereqai

GOOD = "The Transformer uses self-attention and a softmax over the scores of every token in the sequence. " * 2
NOISE = "Xq7#%~ zkvt |||\\^^ ~~ ptkrxz bnmqtw Transformer ;;; @@ vkq jjx %%$ ^^ ~~ qqzx "


def scan(path, regions=False):
    pdf = pymupdf.open()
    page = pdf.new_page(width=595, height=842)
    pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 400, 300), False)
    pixmap.set_rect(pixmap.irect, (200, 200, 200))
    if regions:
        page.insert_textbox(pymupdf.Rect(60, 60, 540, 300), GOOD, fontsize=11)
        page.insert_image(pymupdf.Rect(80, 420, 520, 740), stream=pixmap.tobytes("png"))
    else:
        page.insert_image(page.rect, stream=pixmap.tobytes("png"))
    pdf.save(path)
    return str(path)


def detect(document):
    paper = ParagraphSegmenter().segment(ScientificSectionParser().parse(document))
    return {c.name for c in RuleBasedConceptDetector().detect(paper).concepts}


def test_quality_separates_prose_and_acronyms_from_noise():
    assert ocr_quality(GOOD) > 0.9 and ocr_quality("RNN MLP SGD CIFAR-10 O(n)") > 0.6
    assert ocr_quality(NOISE) < 0.6 and ocr_quality("") == 0.0


def test_letter_soup_is_rejected_even_though_it_is_made_of_letters():
    """Regression: upside-down text and random noise read as words by shape (0.84 and 0.99 in CI) and so were trusted and never rotated."""
    upside_down = "'uolebedoidyoeg UM YJOMIJSU 9} SUICJ] JUBDSAP JUSIDEID \"SenyjeA oul S]UBIOM S8JOOS BU] JOAO XBWIJOS V/ \"UO!]US}]E-JJ9S UO SOIJoJ JOWUOJSUBI] SU]"
    noise = "BE cae ee e nea hen eee Anzaaes Scieaes oteera Stee he ee arinOeeeeeeancesCawpee ee Mee Seeaeu CoesVeeteeSeeae oeee esas dotsates pee ances eeeet"
    assert ocr_quality(upside_down) < 0.6 and ocr_quality(noise) < 0.6
    assert ocr_quality(GOOD) > 0.9
    assert ocr_quality("The Transformer relies on self-attention. A softmax over the scores weights the values. Gradient descent trains the network with backpropagation.") > 0.9


def test_the_vocabulary_is_left_out_for_other_languages_and_for_very_short_text():
    german = "Die Aufmerksamkeit gewichtet jedes Element der Eingabesequenz mit einem gelernten Gewicht fuer die Ausgabe"
    assert ocr_quality(german) < 0.6 <= ocr_quality(german, english=False)
    assert ocr_quality("Figure 3") >= 0.6  # too few words to judge by vocabulary


def test_an_upside_down_scan_is_turned_and_read(tmp_path):
    asked = []

    def turned(page, box, angle):
        asked.append(angle)
        return GOOD if angle == 180 else NOISE

    document = PDFIngestionEngine(ocr=lambda page: NOISE, rotated_ocr=turned).ingest(scan(tmp_path / "a.pdf"))
    page = document.pages[0]
    assert asked == [90, 180] and page.ocr and page.ocr_rotation == 180 and page.ocr_quality > 0.9
    assert "Transformer" in detect(document)
    assert "turned 180 degrees" in " ".join(_ocr_warning(type("P", (), {"pages": document.pages})()))


def test_an_upright_scan_is_not_turned(tmp_path):
    document = PDFIngestionEngine(ocr=lambda page: GOOD, rotated_ocr=lambda *a: pytest.fail("rotated")).ingest(scan(tmp_path / "b.pdf"))
    assert document.pages[0].ocr_rotation == 0 and document.pages[0].ocr


def test_a_noisy_scan_is_warned_about_and_adds_no_concepts(tmp_path):
    document = PDFIngestionEngine(ocr=lambda page: NOISE, rotated_ocr=lambda *a: NOISE).ingest(scan(tmp_path / "c.pdf"))
    page = document.pages[0]
    assert not page.ocr and page.text == "" and "too noisy" in page.ocr_error
    assert detect(document) == set()  # the word "Transformer" inside the noise is not detected
    assert any("too noisy" in note for note in _ocr_warning(type("P", (), {"pages": document.pages})()))


def test_rotation_attempts_count_against_the_page_budget(tmp_path):
    asked = []
    document = PDFIngestionEngine(ocr=lambda page: NOISE, rotated_ocr=lambda p, b, a: asked.append(a) or NOISE, max_ocr_pages=2).ingest(scan(tmp_path / "d.pdf"))
    assert len(asked) == 1 and "too noisy" in document.pages[0].ocr_error  # 1 page + 1 turn = the budget of 2


def test_a_noisy_or_foreign_region_is_left_out_with_a_warning(tmp_path):
    document = PDFIngestionEngine(ocr=lambda page: "", region_ocr=lambda page, box: NOISE, rotated_ocr=lambda *a: NOISE).ingest(scan(tmp_path / "e.pdf", regions=True))
    page = document.pages[0]
    assert page.ocr_regions == 0 and "too noisy" in page.ocr_warning and "Transformer is" not in page.text.replace("The Transformer uses", "")
    assert "self-attention" in page.text  # the text layer is untouched


def test_a_rotated_region_is_recovered(tmp_path):
    document = PDFIngestionEngine(ocr=lambda page: "", region_ocr=lambda page, box: NOISE,
                                  rotated_ocr=lambda page, box, angle: "Scaled dot-product attention applies a softmax over scores of the queries and keys. " * 2 if angle == 90 else NOISE
                                  ).ingest(scan(tmp_path / "f.pdf", regions=True))
    page = document.pages[0]
    assert page.ocr_regions == 1 and page.ocr_rotation == 90 and "Softmax" in detect(document)


def test_english_is_the_default_and_codes_are_validated(monkeypatch):
    monkeypatch.delenv("PREREQAI_OCR_LANGS", raising=False)
    assert ocr_languages() == ["eng"]
    monkeypatch.setenv("PREREQAI_OCR_LANGS", "  ")
    assert ocr_languages() == ["eng"]
    monkeypatch.setenv("PREREQAI_OCR_LANGS", "eng, DEU+deu chi_sim")
    assert ocr_languages() == ["eng", "deu", "chi_sim"]
    monkeypatch.setenv("PREREQAI_OCR_LANGS", "english")
    with pytest.raises(OcrLanguageError, match="not a Tesseract language code"):
        ocr_languages()


def test_the_configured_languages_reach_tesseract_and_a_missing_pack_is_named(tmp_path, monkeypatch):
    (tmp_path / "eng.traineddata").write_bytes(b"")
    (tmp_path / "deu.traineddata").write_bytes(b"")
    monkeypatch.setattr(pymupdf, "get_tessdata", lambda *a, **k: str(tmp_path))
    seen = []

    class Page:
        def get_textpage_ocr(self, **kwargs):
            seen.append(kwargs["language"])
            return "tp"

        def get_text(self, kind, textpage=None):
            return GOOD

    monkeypatch.delenv("PREREQAI_OCR_LANGS", raising=False)
    default_ocr(Page())
    monkeypatch.setenv("PREREQAI_OCR_LANGS", "eng,deu")
    default_ocr(Page())
    assert seen == ["eng", "eng+deu"]
    monkeypatch.setenv("PREREQAI_OCR_LANGS", "eng,fra,jpn")
    with pytest.raises(OcrLanguageError, match="fra, jpn"):
        default_ocr(Page())
    assert len(seen) == 2  # nothing was recognised in English instead


def test_an_unavailable_language_pack_is_reported_for_a_scan_and_a_region(tmp_path, monkeypatch):
    (tmp_path / "eng.traineddata").write_bytes(b"")
    monkeypatch.setattr(pymupdf, "get_tessdata", lambda *a, **k: str(tmp_path))
    monkeypatch.setenv("PREREQAI_OCR_LANGS", "deu")
    document = PDFIngestionEngine().ingest(scan(tmp_path / "g.pdf"))
    page = document.pages[0]
    assert not page.ocr and page.text == "" and "deu" in page.ocr_error and "not installed" in page.ocr_error
    assert any("deu" in note for note in _ocr_warning(type("P", (), {"pages": document.pages})()))
    mixed = PDFIngestionEngine(ocr=lambda page: "").ingest(scan(tmp_path / "h.pdf", regions=True))
    assert "deu" in mixed.pages[0].ocr_warning and "self-attention" in mixed.pages[0].text
