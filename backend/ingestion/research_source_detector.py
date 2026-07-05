import re

from dataclasses import dataclass
from pathlib import Path


ARXIV_PATTERN = re.compile(
    r"(?:https?://)?(?:www\.)?arxiv\.org/(?:abs|pdf)/([0-9]+\.[0-9]+)",
    re.IGNORECASE,
)

DOI_PATTERN = re.compile(
    r"(?:https?://(?:dx\.)?doi\.org/)?(10\.\d{4,9}/[-._;()/:A-Z0-9]+)",
    re.IGNORECASE,
)


@dataclass
class ResearchSource:

    source_type: str

    identifier: str

    original_input: str


class ResearchSourceDetector:
    """
    Detects the type of research source supplied
    by the user.

    Supported types:

    - Local PDF
    - arXiv URL
    - DOI
    """

    def detect(
        self,
        source: str,
    ) -> ResearchSource:

        source = source.strip()

        arxiv_match = ARXIV_PATTERN.search(source)

        if arxiv_match:

            return ResearchSource(
                source_type="arxiv",
                identifier=arxiv_match.group(1),
                original_input=source,
            )

        doi_match = DOI_PATTERN.search(source)

        if doi_match:

            return ResearchSource(
                source_type="doi",
                identifier=doi_match.group(1),
                original_input=source,
            )

        path = Path(source)

        if path.suffix.lower() == ".pdf":

            return ResearchSource(
                source_type="pdf",
                identifier=str(path),
                original_input=source,
            )

        raise ValueError(
            f"Unsupported research source: {source}"
        )
