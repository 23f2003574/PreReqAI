from dataclasses import dataclass, field

from .workspace_region import (
    WorkspaceRegion,
)


@dataclass
class WorkspacePanel:
    """
    Represents a modular panel that
    can be mounted inside a workspace
    region.
    """

    id: str

    title: str

    region: WorkspaceRegion

    component: str

    visible: bool = True

    metadata: dict = field(
        default_factory=dict,
    )
