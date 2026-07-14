from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionDiagnosticStageKind(
    str,
    Enum,
):
    """
    Distinguishes the kind of execution
    a diagnostic stage represents.
    """

    PROJECTION = (
        "projection"
    )

    INPUT_RESOLUTION = (
        "input_resolution"
    )

    ASSEMBLY = (
        "assembly"
    )
