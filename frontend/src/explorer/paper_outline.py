from dataclasses import (
    dataclass,
    field,
)

from .paper_outline_node import (
    PaperOutlineNode,
)


@dataclass
class PaperOutline:
    """
    Represents the complete hierarchical
    outline of a research paper.
    """

    paper_title: str

    roots: list[
        PaperOutlineNode
    ] = field(
        default_factory=list,
    )
