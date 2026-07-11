from enum import Enum


class WorkspaceRegion(str, Enum):
    """
    Defines the major visual regions
    available inside the research workspace.
    """

    HEADER = "header"

    EXPLORER = "explorer"

    MAIN = "main"

    INSPECTOR = "inspector"

    TIMELINE = "timeline"
