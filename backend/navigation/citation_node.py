from dataclasses import dataclass


@dataclass
class CitationNode:
    """
    Represents one in-text citation.
    """

    identifier: str

    context: str

    section: str

    page: int

    reference_id: str
