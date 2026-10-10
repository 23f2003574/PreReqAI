from enum import (
    Enum,
)


class ResearchWorkspaceAttentionSeverity(
    str,
    Enum,
):
    """
    Describes how urgently a workspace
    attention item deserves surfacing.
    """

    INFO = (
        "info"
    )

    LOW = (
        "low"
    )

    MEDIUM = (
        "medium"
    )

    HIGH = (
        "high"
    )

    CRITICAL = (
        "critical"
    )
