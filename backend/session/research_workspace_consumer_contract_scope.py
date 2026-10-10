from enum import (
    Enum,
)


class ResearchWorkspaceConsumerContractScope(
    str,
    Enum,
):
    """
    Identifies the context a consumer
    contract operates against.
    """

    WORKSPACE = (
        "workspace"
    )

    SESSION = (
        "session"
    )
