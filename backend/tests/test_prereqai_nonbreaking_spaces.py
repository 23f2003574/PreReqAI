import pytest

from backend.ingestion.document_metadata_extractor import DocumentMetadata
from backend.ingestion.pdf_ingestion_engine import RawDocument, RawPage
from backend.ingestion.text_cleaning import clean_pdf_text
from backend.parsing import ScientificSectionParser


@pytest.mark.parametrize("space", ["\u00a0", "\u2002", "\u2003", "\u2009", "\u202f", "\u3000"])
def test_fixed_width_spaces_read_as_plain_spaces(space):
    assert clean_pdf_text(f"graph{space}neural{space}network") == "graph neural network"


def test_zero_width_spaces_are_dropped_and_plain_text_is_unchanged():
    assert clean_pdf_text("Soft\u200bmax") == "Softmax"
    assert clean_pdf_text("1 Introduction\nPlain text.") == "1 Introduction\nPlain text."


def test_numbered_headings_with_no_break_spaces_still_split_sections():
    text = clean_pdf_text("Abstract\nWe study it.\n1\u00a0Introduction\nText.\n2\u00a0Related\u00a0Work\nMore.\n")
    document = RawDocument("p.pdf", DocumentMetadata("t", "a", "", "", "", "", 1), [RawPage(1, text)])
    assert [s.title for s in ScientificSectionParser().parse(document).sections] == ["Abstract", "1 Introduction", "2 Related Work"]
