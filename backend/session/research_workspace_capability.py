from enum import (
    Enum,
)


class ResearchWorkspaceCapability(
    str,
    Enum,
):
    """
    Identifies a stable high-level capability
    exposed by the research workspace.
    """

    SESSIONS = (
        "sessions"
    )

    DISCOVERY = (
        "discovery"
    )

    LINEAGE = (
        "lineage"
    )

    COMPARISON = (
        "comparison"
    )

    ORGANIZATION = (
        "organization"
    )

    ACTIVITY = (
        "activity"
    )

    INSIGHTS = (
        "insights"
    )

    SNAPSHOTS = (
        "snapshots"
    )

    IMPORT = (
        "import"
    )

    INTEGRITY = (
        "integrity"
    )

    CHANGE_FEED = (
        "change_feed"
    )

    SUBSCRIPTIONS = (
        "subscriptions"
    )
