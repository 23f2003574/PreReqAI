class ExecutionRuntimeHandoffError(ValueError):
    """
    Raised when an execution runtime recovery handoff is invalid,
    unknown, or a create, accept, reject, or lookup operation cannot
    be performed.
    """

    pass
