import re

from backend.models import Paper, Citation

from .reference_extractor import REFERENCES_TITLE


CITATION_PATTERN = re.compile(r"\[(\d+)\]")


class CitationExtractor:
    """
    Extracts in-text citation occurrences from
    each paragraph, linking them back to their
    bibliography entry by reference number.
    """

    def extract(
        self,
        paper: Paper,
    ) -> Paper:

        citations = []

        citation_counter = 1

        for paragraph in paper.paragraphs:

            if REFERENCES_TITLE.match(
                paragraph.section_title.strip()
            ):
                continue

            for match in CITATION_PATTERN.finditer(
                paragraph.content
            ):

                citations.append(
                    Citation(
                        citation_id=citation_counter,
                        reference_number=int(
                            match.group(1)
                        ),
                        context=paragraph.content,
                        section=paragraph.section_title,
                    )
                )

                citation_counter += 1

        paper.citations = citations

        return paper
