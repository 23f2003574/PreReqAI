from enum import Enum


class ResearchCheckpointReason(
    str,
    Enum,
):
    """
    Describes why a research session
    checkpoint was created.
    """

    MANUAL = "manual"

    ARTIFACT_CREATED = (
        "artifact_created"
    )

    LEARNING_ACTION_COMPLETED = (
        "learning_action_completed"
    )

    WORKFLOW_PROGRESS = (
        "workflow_progress"
    )

    RESEARCH_OBJECT_CHANGED = (
        "research_object_changed"
    )

    SECTION_CHANGED = (
        "section_changed"
    )

    GRAPH_CONTEXT_CHANGED = (
        "graph_context_changed"
    )

    SESSION_RESTORED = (
        "session_restored"
    )

    APPLICATION_BACKGROUND = (
        "application_background"
    )

    RECOVERY_SAFETY = (
        "recovery_safety"
    )

    CHECKPOINT_RESTORED = (
        "checkpoint_restored"
    )

    SESSION_BRANCHED = (
        "session_branched"
    )
