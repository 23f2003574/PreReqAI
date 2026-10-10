class ExecutionStorageFailoverError(ValueError):
    """
    Raised when an execution storage failover is invalid, unknown, or
    a register, execute, or lookup operation cannot be performed.
    """

    pass
