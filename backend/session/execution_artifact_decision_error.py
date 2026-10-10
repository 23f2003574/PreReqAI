class ExecutionArtifactDecisionError(ValueError):
    """
    Raised when an execution artifact decision is invalid, unknown,
    or a publish, promote, distribute, release, retire, or lookup
    operation cannot be performed.
    """

    pass
