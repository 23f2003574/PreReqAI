class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionCoordinatorError(
    ValueError
):
    """
    Raised when a consumer projection execution capability registry
    transaction fails validation and is therefore never handed to
    the transaction executor.
    """

    pass
