class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergeValidationError(
    ValueError
):
    """
    Raised when a consumer projection execution capability registry
    merge plan cannot be validated at all.

    This occurs when the merge plan itself is missing or when an
    entry is malformed beyond inspection (for example, it lacks the
    fields a decision package is expected to expose). Ordinary
    validation failures - a duplicate or empty projection name -
    are reflected in the merge validation report instead of raising
    this error.
    """

    pass
