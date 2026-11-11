import pytest

from backend.models import Paper, Paragraph
from backend.parsing import CitationExtractor


def _citations(*sections):
    paragraphs = [Paragraph(paragraph_id=i, section_title=title, content=text) for i, (title, text) in enumerate(sections, 1)]
    return CitationExtractor().extract(Paper(source_path="p.pdf", metadata=None, paragraphs=paragraphs)).citations


@pytest.mark.parametrize("heading", ["References", "7 References", "VII. References", "Bibliography", "Works Cited", "7. bibliography"])
def test_bibliography_entries_are_not_in_text_citations(heading):
    found = _citations(("Introduction", "Prior work [1] showed this."), (heading, "[1] A. Vaswani. Attention is all you need."))
    assert [(c.reference_number, c.section) for c in found] == [(1, "Introduction")]


def test_other_sections_still_yield_citations():
    found = _citations(("2 Related Work", "See [4] and [5]."))
    assert [c.reference_number for c in found] == [4, 5]
