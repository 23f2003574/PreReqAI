class ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionPackageError(
    ValueError
):
    """
    Raised when an execution capability decision snapshot and
    consumer response cannot be composed into an execution
    capability decision package.

    Both artifacts must describe the same projection and agree on
    the resolved decision and executability. Composing a mismatched
    pair would produce a meaningless package, so this error is
    raised instead of silently composing them.
    """

    pass
