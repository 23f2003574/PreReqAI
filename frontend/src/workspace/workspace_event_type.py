from enum import Enum


class WorkspaceEventType(str, Enum):
    """
    Represents significant state
    transitions inside the visual
    research workspace.
    """

    PAPER_LOADED = "paper_loaded"

    SECTION_SELECTED = "section_selected"

    OBJECT_SELECTED = "object_selected"

    GRAPH_NODE_SELECTED = (
        "graph_node_selected"
    )

    VIEW_CHANGED = "view_changed"

    ACTION_EXECUTED = "action_executed"

    WORKFLOW_LOADED = "workflow_loaded"

    WORKFLOW_STEP_CHANGED = (
        "workflow_step_changed"
    )

    LEARNING_CONTENT_PRESENTED = (
        "learning_content_presented"
    )

    HISTORY_UPDATED = "history_updated"

    RECOMMENDATIONS_UPDATED = (
        "recommendations_updated"
    )
