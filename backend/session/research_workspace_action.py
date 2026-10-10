from enum import (
    Enum,
)


class ResearchWorkspaceAction(
    str,
    Enum,
):
    """
    Identifies a stable, consumer-meaningful
    operation discoverable across the
    research workspace.
    """

    CREATE_SESSION = (
        "create_session"
    )

    IMPORT_SNAPSHOT = (
        "import_snapshot"
    )

    EXPORT_SNAPSHOT = (
        "export_snapshot"
    )

    REVIEW_INTEGRITY = (
        "review_integrity"
    )

    PREVIEW_REPAIR_PLAN = (
        "preview_repair_plan"
    )

    VIEW_ACTIVITY = (
        "view_activity"
    )

    VIEW_INSIGHTS = (
        "view_insights"
    )

    REVIEW_READINESS = (
        "review_workspace_readiness"
    )

    CREATE_CHECKPOINT = (
        "create_checkpoint"
    )

    CREATE_BRANCH = (
        "create_branch"
    )

    PAUSE_SESSION = (
        "pause_session"
    )

    RESUME_SESSION = (
        "resume_session"
    )

    COMPLETE_SESSION = (
        "complete_session"
    )

    ARCHIVE_SESSION = (
        "archive_session"
    )

    RESTORE_SESSION = (
        "restore_session"
    )

    VIEW_LINEAGE = (
        "view_lineage"
    )

    COMPARE_SESSION = (
        "compare_session"
    )

    MANAGE_TAGS = (
        "manage_tags"
    )

    MANAGE_COLLECTIONS = (
        "manage_collections"
    )
