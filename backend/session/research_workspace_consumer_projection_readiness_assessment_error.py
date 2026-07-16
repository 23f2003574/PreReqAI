class ResearchWorkspaceConsumerProjectionReadinessAssessmentError(
    ValueError
):
    """
    Raised when a readiness transition and impact summary cannot be
    combined into an assessment.

    The two artifacts must describe the same projection and the same
    readiness transition. Combining a mismatched pair would produce
    a meaningless assessment, so this error is raised instead of
    silently combining them.
    """

    pass
