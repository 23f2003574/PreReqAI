from dataclasses import (
    dataclass,
    field,
)

from typing import Any


@dataclass
class WorkspaceState:
    """
    Stores the current visual state
    of the research workspace.
    """

    active_paper: Any = None

    active_session: Any = None

    selected_object: Any = None

    active_region: str = "main"

    active_view: str = "paper"

    metadata: dict = field(
        default_factory=dict,
    )
