import re

from dataclasses import dataclass
from pathlib import Path


# Each pattern must match the whole (stripped) input: a reference inside other
# text is ambiguous and rejected rather than guessed. The arXiv identifier keeps
# its version (v5), since a versioned link asks for that exact version.
# New-style ("1706.03762": YYMM, then 4 digits before 2015 or 5 since) and old-style ("hep-th/9901001", "math.GT/0309136") identifiers, each with an optional version.
_ARXIV_ID = r"(?:[0-9]{4}\.[0-9]{4,5}|[a-z]+(?:-[a-z]+)*(?:\.[a-z]{2})?/[0-9]{7})(?:v[0-9]+)?"
ARXIV_PATTERN = re.compile(
    rf"(?:https?://)?(?:www\.|export\.)?arxiv\.org/(?:abs|pdf|html)/({_ARXIV_ID})(?:\.pdf)?/?(?:[?#]\S*)?",
    re.IGNORECASE,
)
# How a paper is usually cited: "arXiv:1706.03762". The explicit prefix is required: a bare number such as
# 1706.03762 is rejected as ambiguous (it could be a mistyped file name).
ARXIV_ID_PATTERN = re.compile(
    rf"arxiv:\s*({_ARXIV_ID})",
    re.IGNORECASE,
)
URL_SCHEME = re.compile(r"[a-z][a-z0-9+.\-]*://", re.IGNORECASE)
DOI_PATTERN = re.compile(
    r"(?:doi:\s*|https?://(?:www\.|dx\.)?doi\.org/)?(10\.\d{4,9}/[-._;()/:A-Z0-9]+)",
    re.IGNORECASE,
)


def has_dot_segment(doi: str) -> bool:
    """A DOI may contain '.' and '/', but a '.' or '..' path segment is never part of a
    real one and would be resolved away when the DOI is placed in an API URL
    (10.1234/../../members -> /members), so it is not accepted as a DOI."""

    return any(segment in (".", "..") for segment in doi.split("/"))


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

        id_match = ARXIV_ID_PATTERN.fullmatch(source)

        if arxiv_match or id_match:

            return ResearchSource(
                source_type="arxiv",
                identifier=(arxiv_match or id_match).group(1),
                original_input=source,
            )

        doi_match = DOI_PATTERN.fullmatch(source)

        if doi_match and not has_dot_segment(doi_match.group(1)):

            return ResearchSource(
                source_type="doi",
                identifier=doi_match.group(1),
                original_input=source,
            )

        if URL_SCHEME.match(source):

            # Only arXiv and DOI links are downloaded. Any other URL would otherwise be read as a local file path
            # (Path collapses "//": "https:/example.com/p.pdf") and fail as a confusing "no such file".
            raise ValueError(f"Unsupported research source: {source}")

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
