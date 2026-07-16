class ResearchWorkspaceConsumerProjectionReadinessDecisionSnapshotError(
    ValueError
):
    """
    Raised when a readiness transition, impact summary, assessment,
    and response package cannot be composed into a decision snapshot.

    The four artifacts must all describe the same projection, and
    the impact and assessment must describe the same transition the
    snapshot is being built from. Composing a mismatched set would
    produce a meaningless snapshot, so this error is raised instead
    of silently composing them.
    """

    pass
