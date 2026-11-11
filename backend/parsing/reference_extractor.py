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

            if not matches:
                matches = dotted_references(section.content)

            for number, text in matches:

                paper.references.append(
                    PaperReference(
                        reference_number=int(number),
                        raw_text=" ".join(text.split()),
                    )
                )

        return paper
