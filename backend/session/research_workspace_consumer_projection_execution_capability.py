from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionExecutionCapability(
    str,
    Enum,
):
    """
    Classifies the intrinsic executability of a consumer projection,
    independent of scheduling or orchestration.
    """

    CAPABLE = (
        "capable"
    )

    LIMITED = (
        "limited"
    )

    INCAPABLE = (
        "incapable"
    )
