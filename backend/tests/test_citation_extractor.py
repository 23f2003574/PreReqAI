from backend.parsing import CitationExtractor

from backend.models import (
    Paper,
    Paragraph,
)


def test_citation_extractor_finds_in_text_citations():

    extractor = CitationExtractor()

    paper = Paper(

        source_path="paper.pdf",

        metadata=None,

        paragraphs=[
            Paragraph(
                paragraph_id=1,
                section_title="Introduction",
                content="Recurrent models [13] are typically factored along symbol positions [7].",
            ),
        ],
    )

    result = extractor.extract(paper)

    assert len(result.citations) == 2
    assert result.citations[0].reference_number == 13
    assert result.citations[1].reference_number == 7
    assert result.citations[0].section == "Introduction"


def test_citation_extractor_skips_references_section():

    extractor = CitationExtractor()

    paper = Paper(

        source_path="paper.pdf",

        metadata=None,

        paragraphs=[
            Paragraph(
                paragraph_id=1,
                section_title="References",
                content="[13] A. Vaswani et al. Attention is all you need.",
            ),
        ],
    )

    result = extractor.extract(paper)

    assert result.citations == []
