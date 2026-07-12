from dataclasses import (
    dataclass,
    field,
)

from datetime import datetime

from typing import Any


@dataclass
class WorkspaceHistoryEntry:
    """
    Represents one educational
    interaction inside the visual
    research session history.
    """

    id: str

    object_id: str

    object_title: str

    action: str

    timestamp: datetime

    artifact_ids: list[str] = field(
        default_factory=list,
    )

    source: Any = None

    metadata: dict = field(
        default_factory=dict,
    )

    selected: bool = False
