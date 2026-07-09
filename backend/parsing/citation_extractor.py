import re

from backend.models import Paper, Citation


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

            if (
                paragraph.section_title.lower()
                == "references"
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
