"""Fixed-phrase headings such as "Related Literature" start their own section in a generated PDF; numbered headings are unchanged."""
import pymupdf as fitz
import pytest

from backend.ingestion import PDFIngestionEngine
from backend.parsing.scientific_section_parser import SECTION_PATTERN, ScientificSectionParser

pytestmark = pytest.mark.prereqai

TEXT = ("A Paper\n\nAbstract\nWe study sorting.\n\n1 Introduction\nWe sort lists quickly.\n\nRelated Literature\nOthers sorted too.\n\n"
        "Problem Setting\nGiven a list, order it.\n\n2 Method\nWe sort.\n\nFuture Directions\nSort faster.\n")


def test_the_headings_split_sections_and_numbered_headings_still_work(tmp_path):
    document = fitz.open()
    document.new_page().insert_text((72, 72), TEXT, fontsize=11)
    path = tmp_path / "paper.pdf"
    path.write_bytes(document.tobytes())
    paper = ScientificSectionParser().parse(PDFIngestionEngine().ingest(str(path)))
    assert [s.title for s in paper.sections] == [
        "Front Matter", "Abstract", "1 Introduction", "Related Literature", "Problem Setting", "2 Method", "Future Directions"]
    assert "Others sorted too." in paper.sections[3].content


@pytest.mark.parametrize("line", ["Related literature is large.", "Experimental settings vary"])
def test_sentences_are_not_headings(line):
    assert SECTION_PATTERN.search(line) is None
