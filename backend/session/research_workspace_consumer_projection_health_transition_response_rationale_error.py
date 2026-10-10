class ResearchWorkspaceConsumerProjectionHealthTransitionResponseRationaleError(
    ValueError
):
    """
    Raised when an operational assessment and a response directive
    cannot be combined into a rationale.

    This happens when the two artifacts do not describe the same
    execution pair and projection, or when the directive's
    recommendation/priority is not the one already established as
    compatible with the assessment (Commit #8/#9 semantics).
    Combining mismatched or incompatible artifacts would produce a
    meaningless rationale, so this error is raised instead of
    silently combining them.
    """

    pass
