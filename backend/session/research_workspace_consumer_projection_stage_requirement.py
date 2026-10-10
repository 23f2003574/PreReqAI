from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionStageRequirement(
    str,
    Enum,
):
    """
    Distinguishes a stage the parent
    operation cannot omit from one it can
    safely skip under budget pressure.
    """

    MANDATORY = (
        "mandatory"
    )

    OPTIONAL = (
        "optional"
    )
