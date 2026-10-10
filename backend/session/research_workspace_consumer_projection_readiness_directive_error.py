class ResearchWorkspaceConsumerProjectionReadinessDirectiveError(
    ValueError
):
    """
    Raised when a readiness recommendation and priority report
    cannot be combined into a directive.

    The two artifacts must describe the same projection and the same
    recommendation. Combining a mismatched pair would produce a
    meaningless directive, so this error is raised instead of
    silently combining them.
    """

    pass
