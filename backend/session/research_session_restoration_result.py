from dataclasses import (
    dataclass,
    field,
)

from typing import Any


@dataclass
class ResearchSessionRestorationResult:
    """
    Describes the outcome of restoring
    a persisted research session.
    """

    session_id: str

    restored: bool

    restored_object: Any = None

    restored_section: Any = None

    restored_graph_node: Any = None

    unresolved_references: list[
        str
    ] = field(
        default_factory=list,
    )
