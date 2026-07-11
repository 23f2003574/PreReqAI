from enum import Enum


class WorkspaceView(str, Enum):
    """
    Defines the primary visual modes
    of the research workspace.
    """

    PAPER = "paper"

    KNOWLEDGE_GRAPH = (
        "knowledge_graph"
    )

    LEARNING = "learning"
