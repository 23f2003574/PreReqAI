from dataclasses import dataclass


@dataclass
class NavigationNode:
    """
    Represents one navigable node
    inside a research paper.
    """

    id: str

    title: str

    node_type: str

    page: int
