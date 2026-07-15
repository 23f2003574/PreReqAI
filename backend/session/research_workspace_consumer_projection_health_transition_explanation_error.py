class ResearchWorkspaceConsumerProjectionHealthTransitionExplanationError(
    ValueError
):
    """
    Raised when a health transition cannot be explained from the
    given quality signal reports and health transition.

    This happens when the reports and transition do not describe
    the same execution pair and projection - for example, mismatched
    execution IDs, mismatched projection names, or a malformed
    report containing duplicate signal codes. Explaining a mismatched
    or malformed set of artifacts would produce a meaningless result,
    so this error is raised instead.
    """

    pass
