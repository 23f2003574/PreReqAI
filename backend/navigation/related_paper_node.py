from dataclasses import dataclass


@dataclass
class RelatedPaperNode:
    """
    Represents a paper connected to
    the current research paper.
    """

    title: str

    authors: list[str]

    year: int

    abstract: str

    relationship: str

    similarity_score: float
