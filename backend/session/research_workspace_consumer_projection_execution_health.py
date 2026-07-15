from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionExecutionHealth(
    str,
    Enum,
):
    """
    Compact overall health classification of one execution's
    quality signals.

    HEALTHY means no warning or critical quality signals exist.

    ATTENTION means one or more warning signals exist, but no
    critical signals exist.

    CRITICAL means at least one critical signal exists.

    Deliberately kept to three values - not a numeric score, and
    not a finer-grained scale (no GOOD/FAIR/POOR/UNKNOWN/PARTIAL).
    """

    HEALTHY = (
        "healthy"
    )

    ATTENTION = (
        "attention"
    )

    CRITICAL = (
        "critical"
    )
