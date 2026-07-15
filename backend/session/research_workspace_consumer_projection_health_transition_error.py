class ResearchWorkspaceConsumerProjectionHealthTransitionError(
    ValueError
):
    """
    Raised when two consumer projection execution health summaries
    cannot be compared as a transition.

    Health summaries can only be compared when they describe the
    same logical projection. Comparing health across unrelated
    projections would produce a meaningless transition, so this
    error is raised instead of silently comparing them.
    """

    pass
