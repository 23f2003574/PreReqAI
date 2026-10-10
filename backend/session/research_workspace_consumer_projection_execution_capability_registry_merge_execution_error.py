class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryMergeExecutionError(
    ValueError
):
    """
    Raised when a consumer projection execution capability registry
    merge plan cannot be executed.

    This occurs when the registry or merge plan is missing or the
    wrong type, or when the merge plan fails integrity validation
    (for example, it contains duplicate or empty projection names).
    No partial merge is applied when this error is raised.
    """

    pass
