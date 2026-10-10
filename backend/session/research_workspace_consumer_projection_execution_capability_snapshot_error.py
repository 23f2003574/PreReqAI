class ResearchWorkspaceConsumerProjectionExecutionCapabilitySnapshotError(
    ValueError
):
    """
    Raised when an execution capability report and capability
    summary cannot be composed into an execution capability
    snapshot.

    Both artifacts must describe the same projection and agree on
    the resolved capability. Composing a mismatched pair would
    produce a meaningless snapshot, so this error is raised instead
    of silently composing them.
    """

    pass
