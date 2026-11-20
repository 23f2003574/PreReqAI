import re

from backend.models import Paper, Citation

from .reference_extractor import REFERENCES_TITLE
from .reference_metadata_parser import ReferenceMetadataParser


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


_YEAR_TOKEN = r"(?:19|20)\d{2}[a-z]?"
_NAME = r"[A-Z][\w'\u2019\-]+"
# "(Wei et al., 2022; Cobbe et al., 2021a)", "(Smith and Jones, 2019)": each item of a parenthesis that holds names and a year ...
_PARENTHESIS = re.compile(r"\(([^()]*?" + _YEAR_TOKEN + r"[^()]*)\)")
_ITEM = re.compile(rf"(?P<first>{_NAME})(?:\s+(?:and|&)\s+(?P<second>{_NAME})|\s+et\s+al\.?)?,?\s+(?P<year>{_YEAR_TOKEN})\b")
# ... and "Brown et al. (2020)", "Andor et al. (2019, 2020)": the names first, the years in the parenthesis.
_NARRATIVE = re.compile(rf"(?P<first>{_NAME})(?:\s+(?:and|&)\s+(?P<second>{_NAME})|\s+et\s+al\.?)?\s*[(\[](?P<years>{_YEAR_TOKEN}(?:\s*[,;]\s*{_YEAR_TOKEN})*)[)\]]")
# "[Bai et al., 2022]", "[Askell et al., 2021, Bai et al., 2022]": a bracket that holds names and a year (a number-only bracket is a numbered citation, handled elsewhere).
_BRACKET = re.compile(r"\[([^\[\]]*?" + _YEAR_TOKEN + r"[^\[\]]*)\]")


def _surname(author: str) -> str:
    """The family name of an author as a bibliography prints it: "Vaswani, A." or "Ashish Vaswani" or "A. Vaswani"."""
    author = author.strip()
    return (author.split(",")[0] if "," in author else author.split()[-1] if author.split() else "").strip(" .").lower()


def author_year_index(paper: Paper) -> dict:
    """{(first author's surname, year): [(reference number, second author's surname or "")]} for the paper's bibliography entries that give authors and a year."""
    index, parser = {}, ReferenceMetadataParser()
    for reference in paper.references:
        data = parser.parse(reference.raw_text)
        if data["authors"] and data["year"]:
            second = _surname(data["authors"][1]) if len(data["authors"]) > 1 else ""
            index.setdefault((_surname(data["authors"][0]), data["year"]), []).append((reference.reference_number, second))
    return index


def author_year_numbers(text: str, index: dict) -> list:
    """The reference numbers an author-year citation text points to, in order. A citation whose first author and year match several entries is attributed only when its
    second author tells them apart; otherwise it is left out rather than guessed."""
    found = []
    pairs = [(m.group("first"), m.group("second"), m.group("year")) for group in _PARENTHESIS.findall(text) for part in group.split(";") for m in [_ITEM.search(part.strip())] if m]
    pairs += [(m.group("first"), m.group("second"), m.group("year")) for group in _BRACKET.findall(text) for m in _ITEM.finditer(group)]
    for m in _NARRATIVE.finditer(text):
        pairs += [(m.group("first"), m.group("second"), year) for year in re.findall(_YEAR_TOKEN, m.group("years"))]
    for first, second, year in pairs:
        candidates = index.get((first.lower(), int(year[:4])), [])
        if len(candidates) > 1 and second:
            candidates = [c for c in candidates if c[1] == second.lower()]
        if len(candidates) == 1:
            found.append(candidates[0][0])
    return found


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

        index = author_year_index(paper)
        known = {reference.reference_number for reference in paper.references}  # with a bibliography, "[0]" or "[40]" beyond its entries is not a citation

        for paragraph in paper.paragraphs:

            if REFERENCES_TITLE.match(
                paragraph.section_title.strip()
            ):
                continue

            for match in CITATION_PATTERN.finditer(
                paragraph.content
            ):

                for number in reference_numbers(match.group(1)):

                    if known and number not in known:
                        continue

                    citations.append(
                        Citation(
                            citation_id=citation_counter,
                            reference_number=number,
                            context=paragraph.content,
                            section=paragraph.section_title,
                        )
                    )

                    citation_counter += 1

            for number in (author_year_numbers(paragraph.content, index) if index else []):

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
