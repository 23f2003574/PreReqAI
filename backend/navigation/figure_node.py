from dataclasses import dataclass


@dataclass
class FigureNode:
    """
    Represents a navigable figure
    inside a research paper.
    """

    identifier: str

    caption: str

    page: int

    section: str

    image_path: str
