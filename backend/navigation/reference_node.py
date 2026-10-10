from dataclasses import dataclass


@dataclass
class ReferenceNode:
    """
    Represents a bibliography entry
    inside a research paper.
    """

    identifier: str

    title: str

    authors: list[str]

    year: int

    venue: str

    doi: str

    abstract: str
