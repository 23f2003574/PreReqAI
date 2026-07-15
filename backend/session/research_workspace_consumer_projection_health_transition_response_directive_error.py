class ResearchWorkspaceConsumerProjectionHealthTransitionResponseDirectiveError(
    ValueError
):
    """
    Raised when a response recommendation and a response priority
    result cannot be combined into a directive.

    This happens when the two artifacts do not describe the same
    execution pair, projection, or recommendation kind. Combining
    mismatched artifacts would produce a meaningless directive, so
    this error is raised instead of silently combining them.
    """

    pass
