class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryHealthAnalysisError(
    ValueError
):
    """
    Raised when a consumer projection execution capability registry
    cannot be analyzed for health.

    This occurs when the registry itself is missing or when a
    stored entry is malformed beyond inspection (for example, it
    lacks the fields a decision package is expected to expose).
    """

    pass
