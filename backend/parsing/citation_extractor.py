import re

from backend.models import Paper, Citation

from .reference_extractor import REFERENCES_TITLE


# "[13]", a list "[1, 2]" / "[1,2,3]", a range "[1-3]" (hyphen or en dash), or a mix "[1, 3-5]".
CITATION_PATTERN = re.compile(r"\[(\d+(?:\s*(?:,|-|\u2013)\s*\d+)*)\]")
_PART_SEPARATOR = re.compile(r"\s*,\s*")
_RANGE_SEPARATOR = re.compile(r"\s*[-\u2013]\s*")
YEAR_LIKE = 1000  # a list or range reaching this ("[2019-2021]", "[2018, 2020]") is years, not reference numbers
MAX_RANGE_SIZE = 500  # a longer range is a typo or not a citation, not worth that many records


def reference_numbers(group: str) -> list[int]:
    """The reference numbers a citation's bracket text lists, in order; a reversed or oversized range contributes none."""
    numbers = []
    for part in _PART_SEPARATOR.split(group):
        bounds = [int(bound) for bound in _RANGE_SEPARATOR.split(part)]
        if len(bounds) == 1:
            if bounds[0] < YEAR_LIKE or group.isdigit():  # a lone "[1999]" is still one citation, as before
                numbers.append(bounds[0])
        elif len(bounds) == 2 and 0 <= bounds[1] - bounds[0] < MAX_RANGE_SIZE and bounds[1] < YEAR_LIKE:
            numbers.extend(range(bounds[0], bounds[1] + 1))
    return numbers


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

                for number in reference_numbers(match.group(1)):

                    citations.append(
                        Citation(
                            citation_id=citation_counter,
                            reference_number=number,
                            context=paragraph.content,
                            section=paragraph.section_title,
                        )
                    )

                    citation_counter += 1

        paper.citations = citations

        return paper
