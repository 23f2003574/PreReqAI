class ResearchWorkspaceConsumerProjectionExecutionCapabilitySnapshotPackageError(
    ValueError
):
    """
    Raised when an execution capability snapshot and capability
    descriptor cannot be composed into an execution capability
    snapshot package.

    Both artifacts must describe the same projection and agree on
    whether the projection is executable. Composing a mismatched
    pair would produce a meaningless package, so this error is
    raised instead of silently composing them.
    """

    pass
