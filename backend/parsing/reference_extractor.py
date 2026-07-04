import re

from backend.models import Paper, PaperReference


REFERENCE_PATTERN = re.compile(
    r"^\[(\d+)\]\s+(.+)$",
    re.MULTILINE,
)


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

            if section.title.lower() != "references":
                continue

            matches = REFERENCE_PATTERN.findall(
                section.content
            )

            for number, text in matches:

                paper.references.append(
                    PaperReference(
                        reference_number=int(number),
                        raw_text=text.strip(),
                    )
                )

        return paper
