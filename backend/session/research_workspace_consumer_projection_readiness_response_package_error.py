class ResearchWorkspaceConsumerProjectionReadinessResponsePackageError(
    ValueError
):
    """
    Raised when a readiness directive and readiness rationale cannot
    be combined into a response package.

    The two artifacts must describe the same projection and agree on
    recommendation and priority. Combining a mismatched pair would
    produce a meaningless response package, so this error is raised
    instead of silently combining them.
    """

    pass
