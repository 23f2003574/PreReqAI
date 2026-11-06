"""IEEE-style title-case headings with a roman numeral ("II. Proposed Method") start a section; author lines do not."""
import pytest

from backend.parsing.scientific_section_parser import SECTION_PATTERN

pytestmark = pytest.mark.prereqai


@pytest.mark.parametrize("line", ["II. Proposed Method", "V. Implementation Of The System", "IX. Results on Benchmarks"])
def test_roman_numbered_title_case_headings_are_recognised(line):
    assert SECTION_PATTERN.fullmatch(line)


@pytest.mark.parametrize("line", ["I. Goodfellow", "I. Goodfellow and Y. Bengio", "V. Kumar", "II. Proposed method uses 3 layers"])
def test_author_lines_and_sentences_are_not_headings(line):
    assert not SECTION_PATTERN.fullmatch(line)


def test_the_section_text_is_split_at_such_a_heading(tmp_path):
    import pymupdf

    from backend.ingestion import PDFIngestionEngine
    from backend.parsing import ScientificSectionParser

    document = pymupdf.open()
    document.new_page().insert_text((72, 72), "A Paper\n\nAbstract\nWe sort.\n\nII. Proposed Method\nWe use softmax.\n\nIII. Experimental Results\nIt works.\n", fontsize=11)
    path = tmp_path / "p.pdf"
    document.save(path)
    titles = [s.title for s in ScientificSectionParser().parse(PDFIngestionEngine().ingest(str(path))).sections]
    assert titles == ["Front Matter", "Abstract", "II. Proposed Method", "III. Experimental Results"]
