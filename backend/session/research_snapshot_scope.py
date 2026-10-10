from enum import (
    Enum,
)


class ResearchSnapshotScope(
    str,
    Enum,
):
    """
    Defines the domain boundary included
    in a portable research snapshot.
    """

    SESSION = (
        "session"
    )

    SESSION_WITH_DESCENDANTS = (
        "session_with_descendants"
    )

    LINEAGE = (
        "lineage"
    )

    WORKSPACE = (
        "workspace"
    )
