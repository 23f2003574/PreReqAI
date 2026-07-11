from dataclasses import (
    dataclass,
    field,
)

from typing import Any


@dataclass
class PaperOutlineNode:
    """
    Represents one navigable node
    inside the paper outline.
    """

    id: str

    title: str

    level: int

    section_number: str | None = None

    page: int | None = None

    source: Any = None

    children: list[
        "PaperOutlineNode"
    ] = field(
        default_factory=list,
    )

    expanded: bool = True
