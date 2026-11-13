"""Running headers, footers and page numbers repeat on many pages: they are removed before concepts are counted, and body text is kept."""
import pymupdf
import pytest

from backend.ingestion import PDFIngestionEngine
from backend.ingestion.text_cleaning import drop_repeated_page_lines
from backend.platform import platform

pytestmark = pytest.mark.prereqai


WORDS = ["north", "river", "stone", "amber", "violet", "harbor", "meadow", "copper", "lantern", "fabric", "glacier", "willow", "ember",
         "quartz", "thistle", "marble", "saffron", "orchid", "pebble", "cobalt", "juniper", "velvet", "granite"]


def body(n, count=6):
    """`count` body lines whose words differ from page to page, as real body text does."""
    return [" ".join(WORDS[(n * a + k * b + c) % len(WORDS)] for a, b, c in ((11, 3, 0), (5, 7, 1), (1, 13, 2))) for k in range(count)]


def page(*lines):
    return "".join(line + "\n" for line in lines)


def test_a_header_a_footer_and_page_numbers_that_repeat_are_removed():
    texts = [page("Journal of Graph Learning", *body(n), f"{n}") for n in range(1, 7)]
    cleaned, removed = drop_repeated_page_lines(texts)
    assert removed == [2] * 6  # header and number on each page
    assert cleaned[2] == page(*body(3))


def test_page_number_forms_and_a_digit_bearing_header_repeat_across_pages():
    texts = [page(f"Smith et al. {2000 + n}", *body(n), f"Page {n} of 6") for n in range(1, 7)]
    cleaned, removed = drop_repeated_page_lines(texts)
    assert removed == [2] * 6 and cleaned[0] == page(*body(1))


def test_alternating_even_and_odd_headers_are_removed():
    texts = [page("Attention Is All You Need" if n % 2 else "Vaswani et al.", *body(n)) for n in range(1, 9)]
    assert drop_repeated_page_lines(texts)[1] == [1] * 8


def test_a_line_repeated_in_the_body_is_kept():
    repeated = "We use attention. We use attention."
    texts = [page(f"Heading {n}", *body(n, 3), repeated, *body(n + 20, 3), f"closing {n}") for n in range(1, 7)]
    cleaned, removed = drop_repeated_page_lines(texts)
    assert all(repeated in text for text in cleaned) and removed == [2] * 6  # "Heading #" and "closing #" go; the repeated body line stays


def test_a_line_that_only_some_pages_open_with_is_kept():
    texts = [page("Introduction" if n == 1 else body(n, 1)[0], *body(n + 9)) for n in range(1, 7)]
    assert drop_repeated_page_lines(texts)[1] == [0] * 6


def test_documents_of_one_or_two_pages_are_left_alone():
    texts = [page("Header", *body(1), "1"), page("Header", *body(2), "2")]
    assert drop_repeated_page_lines(texts) == (texts, [0, 0])


def make_pdf(path, pages):
    pdf = pymupdf.open()
    for n in range(1, pages + 1):
        sheet = pdf.new_page()
        sheet.insert_text((72, 40), "Attention Mechanisms Review", fontsize=9)
        for k, line in enumerate(body(n, 8)):
            sheet.insert_text((72, 100 + 20 * k), line, fontsize=11)
        sheet.insert_text((290, 800), str(n), fontsize=9)
    pdf.save(path)


def test_the_ingestion_engine_removes_them_and_records_how_many(tmp_path):
    path = tmp_path / "p.pdf"
    make_pdf(str(path), 5)
    document = PDFIngestionEngine().ingest(str(path))
    assert [p.removed_lines for p in document.pages] == [2] * 5
    assert "Attention Mechanisms Review" not in document.full_text and body(3)[0] in document.full_text


def test_a_repeated_concept_header_no_longer_inflates_mentions_or_coverage(tmp_path):
    path = tmp_path / "p.pdf"
    make_pdf(str(path), 5)  # "Attention" is in every page's header, and the body never names it
    outcome = platform.analyze(str(path))
    assert outcome["status"] == "success"
    assert not [c for c in outcome["report"]["concepts"] if c == "Attention"]
    assert any("Removed 10 repeated header, footer or page-number lines" in w for w in outcome["warnings"])


def test_normal_text_pdfs_are_extracted_as_before_and_one_page_gets_no_warning():
    outcome = platform.analyze("examples/prerequisites/sample-paper.pdf")
    assert outcome["warnings"] == []
    document = PDFIngestionEngine().ingest("examples/prerequisites/sample-paper.pdf")
    assert [p.removed_lines for p in document.pages] == [0]
