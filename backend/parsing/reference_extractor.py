import re

from backend.models import Paper, PaperReference


REFERENCE_PATTERN = re.compile(
    r"\[(\d+)\]\s+(.+?)(?=\n\[\d+\]|\Z)",
    re.DOTALL,
)


# A bibliography numbered "1. Author. Title." instead of "[1] ...". An entry starts only at the next number in sequence (1, 2, 3...), so a
# wrapped line that happens to start with a year ("2017. NeurIPS.") stays part of the entry it belongs to.
_DOTTED_ENTRY = re.compile(r"^\s*(\d{1,3})\.\s+(\S.*)$")


def dotted_references(content: str) -> list:
    entries, expected = [], 1
    for line in content.splitlines():
        match = _DOTTED_ENTRY.match(line)
        if match and int(match.group(1)) == expected:
            entries.append((expected, [match.group(2)]))
            expected += 1
        elif entries and line.strip():
            entries[-1][1].append(line)
    return [(number, " ".join(lines)) for number, lines in entries]


# An unnumbered bibliography in author-year style ("Aida Amini, Saadia Gabriel, and Hannaneh Hajishirzi. 2019. MathQA: ..."). An entry is finished once it holds a year; a new entry
# starts at a line that opens like a list of names (capitalised words, then a comma or "and") after a line that ends a sentence. Wrapped lines of one entry stay together.
_YEAR = re.compile(r"\b(?:19|20)\d{2}[a-z]?\b")
_NAME_START = re.compile(r"^[A-Z][\w'\u2019\-]*(?:\.|\s+[A-Z][\w'\u2019\-]*\.?){0,3},|^[A-Z][\w'\u2019\-]*(?:\s+[A-Z][\w'\u2019\-]*\.?){1,3}\s+and\s+[A-Z]")
MIN_ENTRIES = 5


def author_year_entries(content: str) -> list:
    """[(number, text)] for the entries of an unnumbered author-year bibliography, numbered in order; [] when the text does not look like one (fewer than MIN_ENTRIES entries)."""
    entries, current = [], []
    for line in (raw.strip() for raw in content.splitlines()):
        if not line:
            continue
        done = current and _YEAR.search(" ".join(current)) and " ".join(current).rstrip().endswith((".", ")")) or (current and re.search(r"\d\.?$", " ".join(current)))
        if current and done and _NAME_START.match(line):
            entries.append(" ".join(current))
            current = []
        current.append(line)
    if current:
        entries.append(" ".join(current))
    entries = [entry for entry in entries if _YEAR.search(entry)]
    return [(number, text) for number, text in enumerate(entries, start=1)] if len(entries) >= MIN_ENTRIES else []


# The titles ScientificSectionParser accepts for the bibliography, with an optional section number ("7", "7.", "VII.") and a trailing colon.
REFERENCES_TITLE = re.compile(r"^(?:\d+(?:\.\d+)*\.?|[IVXivx]+\.)?\s*(?:references|bibliography|works cited)\s*:?\s*$", re.IGNORECASE)


class ReferenceExtractor:
    """
    Extracts bibliography entries from the
    References section of a research paper.

    This stage only records the raw reference.
    DOI/arXiv resolution will be implemented later.
    """

    def extract(
        self,
        paper: Paper,
    ) -> Paper:

        for section in paper.sections:

            if not REFERENCES_TITLE.match(section.title.strip()):
                continue

            matches = REFERENCE_PATTERN.findall(
                section.content
            )

            if len(matches) < MIN_ENTRIES:
                matches = dotted_references(section.content) or matches
            unnumbered = author_year_entries(section.content)
            if len(unnumbered) > 2 * len(matches):  # a few "[1]" marks in a checklist after an author-year bibliography are not the bibliography
                matches = unnumbered

            for number, text in matches:

                paper.references.append(
                    PaperReference(
                        reference_number=int(number),
                        raw_text=" ".join(text.split()),
                    )
                )

        return paper
