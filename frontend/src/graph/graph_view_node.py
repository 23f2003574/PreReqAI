from dataclasses import (
    dataclass,
    field,
)

from typing import Any


@dataclass
class GraphViewNode:
    """
    Represents one visual node inside
    the knowledge graph workspace.
    """

    id: str

    label: str

    node_type: str

    description: str = ""

    source: Any = None

    metadata: dict = field(
        default_factory=dict,
    )

    selected: bool = False
