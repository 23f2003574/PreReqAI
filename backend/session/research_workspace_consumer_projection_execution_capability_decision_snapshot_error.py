class ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionSnapshotError(
    ValueError
):
    """
    Raised when an execution capability decision report and decision
    summary cannot be composed into an execution capability decision
    snapshot.

    Both artifacts must describe the same projection and agree on
    the resolved decision and reason. Composing a mismatched pair
    would produce a meaningless snapshot, so this error is raised
    instead of silently composing them.
    """

    pass
