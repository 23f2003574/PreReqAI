from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionQualitySignalSeverity(
    str,
    Enum,
):
    """
    Deterministic severity of one execution quality signal.

    INFO means a notable execution condition that does not
    necessarily reduce result reliability.

    WARNING means execution quality or completeness was reduced,
    but a valid projection was still produced.

    CRITICAL means a severe condition exists in the completed
    execution receipt.

    A CRITICAL signal does not imply the whole projection is
    invalid - receipt verification remains a separate concern.
    """

    INFO = (
        "info"
    )

    WARNING = (
        "warning"
    )

    CRITICAL = (
        "critical"
    )
