class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionError(
    ValueError
):
    """
    Raised when a consumer projection execution capability registry
    transaction cannot be executed.

    This occurs when the registry or transaction is missing or the
    wrong type, an entry has an empty projection name or an invalid
    operation, entries conflict by targeting the same projection
    more than once, or an entry's operation cannot be satisfied
    against the current registry state (for example, REGISTER on an
    already-registered projection). No partial transaction is
    applied when this error is raised.
    """

    pass
