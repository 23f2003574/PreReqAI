class ResearchWorkspaceConsumerProjectionHealthTransitionResponsePackageError(
    ValueError
):
    """
    Raised when a response directive and a response rationale cannot
    be combined into a response package.

    This happens when the two artifacts do not describe the same
    execution pair and projection, or when their recommendation or
    priority disagree. The package builder never repairs an
    inconsistent pair - it raises instead of silently combining them.
    """

    pass
