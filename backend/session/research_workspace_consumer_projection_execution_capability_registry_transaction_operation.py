from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionOperation(
    str,
    Enum,
):
    """
    The kind of change a single transaction entry applies to a
    consumer projection execution capability registry.
    """

    REGISTER = (
        "register"
    )

    UPDATE = (
        "update"
    )

    REMOVE = (
        "remove"
    )
