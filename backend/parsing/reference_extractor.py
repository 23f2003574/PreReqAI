import re

from backend.models import Paper, PaperReference


REFERENCE_PATTERN = re.compile(
    r"\[(\d+)\]\s+(.+?)(?=\n\[\d+\]|\Z)",
    re.DOTALL,
)


# The titles ScientificSectionParser accepts for the bibliography, with an optional section number ("7", "7.", "VII.").
REFERENCES_TITLE = re.compile(r"^(?:\d+(?:\.\d+)*\.?|[IVXivx]+\.)?\s*(?:references|bibliography|works cited)\s*$", re.IGNORECASE)


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

            for number, text in matches:

                paper.references.append(
                    PaperReference(
                        reference_number=int(number),
                        raw_text=" ".join(text.split()),
                    )
                )

        return paper
