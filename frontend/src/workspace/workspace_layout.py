from dataclasses import dataclass


@dataclass(frozen=True)
class WorkspaceLayout:
    """
    Defines the structural layout
    of the visual research workspace.
    """

    header: str = "workspace-header"

    explorer: str = "workspace-explorer"

    main: str = "workspace-main"

    inspector: str = "workspace-inspector"

    timeline: str = "workspace-timeline"
