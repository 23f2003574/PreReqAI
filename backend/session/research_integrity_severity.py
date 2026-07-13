from enum import (
    Enum,
)


class ResearchIntegritySeverity(
    str,
    Enum,
):
    """
    Describes the operational severity
    of a workspace integrity finding.
    """

    INFO = (
        "info"
    )

    WARNING = (
        "warning"
    )

    ERROR = (
        "error"
    )

    CRITICAL = (
        "critical"
    )
