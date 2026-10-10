class ResearchWorkspaceConsumerProjectionExecutionDecisionPackageError(
    ValueError
):
    """
    Raised when an execution snapshot and consumer response cannot
    be composed into an execution decision package.

    Both artifacts must describe the same projection. Composing a
    mismatched pair would produce a meaningless package, so this
    error is raised instead of silently composing them.
    """

    pass
