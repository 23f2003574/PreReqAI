"""Authors printed one per line (or in several lines) on page one are all found when the PDF metadata has none."""
import pymupdf

from backend.ingestion.document_metadata_extractor import DocumentMetadataExtractor


def _author(tmp_path, *lines):
    doc = pymupdf.open()
    page = doc.new_page()
    for number, text in enumerate(lines):
        page.insert_text((72, 72 + 18 * number), text, fontsize=16 if number == 0 else 10)
    path = tmp_path / "p.pdf"
    doc.save(path)
    return DocumentMetadataExtractor().extract(str(path)).author


def test_authors_on_separate_lines_are_joined_and_stop_at_the_affiliation(tmp_path):
    assert _author(tmp_path, "Attention Is All You Need", "Ashish Vaswani", "Noam Shazeer*", "Niki Parmar, Jakob Uszkoreit",
                   "Google Brain", "Abstract", "We propose a model.") == "Ashish Vaswani, Noam Shazeer, Niki Parmar, Jakob Uszkoreit"


def test_a_single_author_line_still_works_and_no_author_lines_stay_unknown(tmp_path):
    assert _author(tmp_path, "A Title", "Jane Doe and John Smith", "Department of Things") == "Jane Doe, John Smith"
    assert _author(tmp_path, "A Title", "Abstract", "we study things", "Department of Things") == "Unknown Author"
