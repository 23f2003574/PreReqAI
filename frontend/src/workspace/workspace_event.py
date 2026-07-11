from dataclasses import (
    dataclass,
    field,
)

from datetime import datetime

from typing import Any

from .workspace_event_type import (
    WorkspaceEventType,
)


@dataclass
class WorkspaceEvent:
    """
    Represents one significant event
    occurring inside the research
    workspace.
    """

    event_type: WorkspaceEventType

    payload: Any = None

    metadata: dict = field(
        default_factory=dict,
    )

    timestamp: datetime = field(
        default_factory=datetime.utcnow,
    )
