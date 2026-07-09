from dataclasses import dataclass


@dataclass
class ConceptNode:
    """
    Represents a navigable research concept.
    """

    name: str

    description: str

    section: str

    page: int

    importance: float
