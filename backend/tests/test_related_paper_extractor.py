from backend.parsing import RelatedPaperExtractor

from backend.models import (
    Paper,
    PaperReference,
)


def test_related_paper_extractor_derives_from_references():

    extractor = RelatedPaperExtractor()

    paper = Paper(

        source_path="paper.pdf",

        metadata=None,

        references=[
            PaperReference(
                reference_number=13,
                raw_text=(
                    "Sepp Hochreiter and Jurgen Schmidhuber. "
                    "Long short-term memory. "
                    "Neural computation, 9(8):1735-1780, 1997."
                ),
            ),
        ],
    )

    result = extractor.extract(paper)

    assert len(result.related_papers) == 1

    related = result.related_papers[0]

    assert related.reference_number == 13
    assert related.title == "Long short-term memory"
    assert related.authors == [
        "Sepp Hochreiter",
        "Jurgen Schmidhuber",
    ]
    assert related.year == 1997
    assert related.relationship == "cites"
    assert related.similarity_score is None
