import re

from dataclasses import dataclass
from pathlib import Path


# Each pattern must match the whole (stripped) input: a reference inside other
# text is ambiguous and rejected rather than guessed. The arXiv identifier keeps
# its version (v5), since a versioned link asks for that exact version.
ARXIV_PATTERN = re.compile(
    r"(?:https?://)?(?:www\.)?arxiv\.org/(?:abs|pdf)/([0-9]+\.[0-9]+(?:v[0-9]+)?)(?:\.pdf)?/?",
    re.IGNORECASE,
)

DOI_PATTERN = re.compile(
    r"(?:doi:\s*|https?://(?:dx\.)?doi\.org/)?(10\.\d{4,9}/[-._;()/:A-Z0-9]+)",
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

        local_path = Path(source)

        if local_path.suffix.lower() == ".pdf" and local_path.is_file():

            # An existing local PDF is always a local PDF, even when its
            # path happens to contain an arXiv- or DOI-looking segment
            # (e.g. papers/10.1145/3292500.pdf).
            return ResearchSource(
                source_type="pdf",
                identifier=str(local_path),
                original_input=source,
            )

        arxiv_match = ARXIV_PATTERN.fullmatch(source)

        if arxiv_match:

            return ResearchSource(
                source_type="arxiv",
                identifier=arxiv_match.group(1),
                original_input=source,
            )

        doi_match = DOI_PATTERN.fullmatch(source)

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
