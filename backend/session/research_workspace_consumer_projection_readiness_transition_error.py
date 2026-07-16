class ResearchWorkspaceConsumerProjectionReadinessTransitionError(
    ValueError
):
    """
    Raised when two consumer projection readiness reports cannot be
    compared as a transition.

    Readiness reports can only be compared when they describe the
    same logical projection. Comparing readiness across unrelated
    projections would produce a meaningless transition, so this
    error is raised instead of silently comparing them.
    """

    pass
