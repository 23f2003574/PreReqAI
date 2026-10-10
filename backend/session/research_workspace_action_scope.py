from enum import (
    Enum,
)


class ResearchWorkspaceActionScope(
    str,
    Enum,
):
    """
    Identifies the kind of context an
    action's availability is evaluated
    against.
    """

    WORKSPACE = (
        "workspace"
    )

    SESSION = (
        "session"
    )
