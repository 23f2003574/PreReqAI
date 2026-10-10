class ResearchWorkspaceConsumerProjectionExecutionReadinessSnapshotError(
    ValueError
):
    """
    Raised when an execution lifecycle report and execution summary
    cannot be composed into an execution readiness snapshot.

    Both artifacts must describe the same projection. Composing a
    mismatched pair would produce a meaningless snapshot, so this
    error is raised instead of silently composing them.
    """

    pass
