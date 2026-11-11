import pytest

from backend.ingestion import RawDocument, RawPage
from backend.ingestion.document_metadata_extractor import DocumentMetadata
from backend.parsing import CitationExtractor, ParagraphSegmenter, ReferenceExtractor, ScientificSectionParser


def _analyse(heading):
    text = f"Title\n\nIntroduction\nWe build on prior work [1].\n\n{heading}\n[1] A. Vaswani. Attention is all you need.\n[2] B. Other. Second paper.\n"
    document = RawDocument("p.pdf", DocumentMetadata("T", "A", "", "", "", "", 1), [RawPage(1, text)])
    paper = ScientificSectionParser().parse(document)
    return CitationExtractor().extract(ReferenceExtractor().extract(ParagraphSegmenter().segment(paper)))


@pytest.mark.parametrize("heading", ["References", "References:", "REFERENCES:", "7 References:", "Bibliography:", "Works Cited:"])
def test_a_bibliography_heading_with_a_colon_still_yields_references_and_no_bibliography_citations(heading):
    paper = _analyse(heading)
    assert [r.reference_number for r in paper.references] == [1, 2]
    assert [c.reference_number for c in paper.citations] == [1]
