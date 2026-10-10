class ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentError(
    ValueError
):
    """
    Raised when a health transition and a transition impact summary
    cannot be assessed together.

    This happens when the two artifacts do not describe the same
    execution pair, projection, or transition kind. Combining
    mismatched artifacts would produce a meaningless assessment, so
    this error is raised instead of silently combining them.
    """

    pass
