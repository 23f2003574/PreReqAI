from backend.models import Paper, RelatedPaper

from .reference_metadata_parser import (
    ReferenceMetadataParser,
)


class RelatedPaperExtractor:
    """
    Derives related papers from the paper's own
    bibliography. Every related paper here is
    "cites" by construction (the only relationship
    this data can honestly support) — richer
    relationships (extends/inspired by/competes
    with) and real similarity scoring need an
    external literature source this project
    doesn't have yet.
    """

    def __init__(self):

        self.metadata_parser = (
            ReferenceMetadataParser()
        )

    def extract(
        self,
        paper: Paper,
    ) -> Paper:

        related_papers = []

        for reference in paper.references:

            metadata = self.metadata_parser.parse(
                reference.raw_text
            )

            related_papers.append(
                RelatedPaper(
                    reference_number=(
                        reference.reference_number
                    ),
                    title=(
                        metadata["title"]
                        or reference.raw_text
                    ),
                    authors=metadata["authors"],
                    year=metadata["year"],
                    relationship="cites",
                    similarity_score=None,
                )
            )

        paper.related_papers = related_papers

        return paper
