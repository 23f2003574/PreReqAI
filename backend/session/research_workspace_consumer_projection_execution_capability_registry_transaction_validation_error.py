class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionValidationError(
    ValueError
):
    """
    Raised when a consumer projection execution capability registry
    transaction cannot be validated at all.

    This occurs when the transaction itself is missing or when an
    entry is malformed beyond inspection (for example, it lacks the
    fields an operation or decision package is expected to expose).
    Ordinary validation failures - a duplicate or empty projection
    name, an invalid operation, an invalid package - are reflected
    in the validation report instead of raising this error.
    """

    pass
