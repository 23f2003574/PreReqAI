class ResearchWorkspaceConsumerProjectionReadinessExplanationError(
    ValueError
):
    """
    Raised when a readiness transition cannot be explained from the
    given previous report, current report, and transition report.

    The three inputs must all describe the same projection, and the
    transition report must actually describe the readiness movement
    between the two given reports. Explaining a mismatched triple
    would produce a meaningless explanation, so this error is raised
    instead of silently explaining them.
    """

    pass
