class ResearchWorkspaceConsumerProjectionExecutionSnapshotError(
    ValueError
):
    """
    Raised when the eligibility, decision, gate, authorization,
    verdict, and summary reports cannot be composed into an
    execution snapshot.

    All six artifacts must describe the same projection. Composing
    a mismatched set would produce a meaningless snapshot, so this
    error is raised instead of silently composing them.
    """

    pass
