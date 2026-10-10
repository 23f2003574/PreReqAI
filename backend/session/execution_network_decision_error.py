class ExecutionNetworkDecisionError(ValueError):
    """
    Raised when an execution network decision is invalid, unknown, or
    a connect, evaluate, reroute, disconnect, or lookup operation
    cannot be performed.
    """

    pass
