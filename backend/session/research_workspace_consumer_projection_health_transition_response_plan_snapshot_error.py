class ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanSnapshotError(
    ValueError
):
    """
    Raised when the transition, impact summary, assessment, and
    response package cannot be combined into a response plan
    snapshot.

    This happens when the artifacts do not describe the same
    execution pair and projection, or when they disagree on the
    decisions they share (e.g. the impact summary's transition kind
    does not match the transition itself, or the response package's
    recommendation is not the one already established as compatible
    with the assessment). The snapshot builder never repairs an
    inconsistent decision chain - it raises instead of silently
    combining mismatched artifacts.
    """

    pass
