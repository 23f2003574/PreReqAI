from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionExecutionDecision(
    str,
    Enum,
):
    """
    Classifies what should happen next for a consumer projection,
    having already been evaluated for execution eligibility.
    """

    EXECUTE = (
        "execute"
    )

    WAIT_FOR_APPROVAL = (
        "wait_for_approval"
    )

    DO_NOT_EXECUTE = (
        "do_not_execute"
    )
