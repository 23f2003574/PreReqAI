class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistrySnapshotError(
    ValueError
):
    """
    Raised when a consumer projection execution capability registry
    snapshot cannot be built.

    This occurs when the registry itself is missing or when a
    stored entry is not a valid execution capability decision
    package. Building a snapshot from such a registry would produce
    a meaningless read model, so this error is raised instead of
    silently building one.
    """

    pass
