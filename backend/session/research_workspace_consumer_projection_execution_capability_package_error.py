class ResearchWorkspaceConsumerProjectionExecutionCapabilityPackageError(
    ValueError
):
    """
    Raised when an execution capability snapshot cannot be composed
    into an execution capability package.

    The snapshot's projection name must be non-empty. Composing a
    package with no identifiable projection would produce a
    meaningless consumer-facing artifact, so this error is raised
    instead of silently composing it.
    """

    pass
