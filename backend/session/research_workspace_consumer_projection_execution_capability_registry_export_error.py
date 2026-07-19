class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryExportError(
    ValueError
):
    """
    Raised when a consumer projection execution capability registry
    cannot be exported.

    This occurs when the registry itself is missing or when a
    stored entry is not a valid execution capability decision
    package. Exporting such a registry would produce a meaningless
    portable representation, so this error is raised instead of
    silently exporting one.
    """

    pass
