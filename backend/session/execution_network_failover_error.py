class ExecutionNetworkFailoverError(ValueError):
    """
    Raised when an execution network failover is invalid, unknown, or
    a register, execute, select, or lookup operation cannot be
    performed.
    """

    pass
