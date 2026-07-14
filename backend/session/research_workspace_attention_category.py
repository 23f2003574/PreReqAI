from enum import (
    Enum,
)


class ResearchWorkspaceAttentionCategory(
    str,
    Enum,
):
    """
    Groups workspace attention items by
    the subsystem that produced them.
    """

    READINESS = (
        "readiness"
    )

    INTEGRITY = (
        "integrity"
    )

    RESEARCH_SESSION = (
        "research_session"
    )
