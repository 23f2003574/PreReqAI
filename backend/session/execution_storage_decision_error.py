class ExecutionStorageDecisionError(ValueError):
    """
    Raised when an execution storage decision is invalid, unknown, or
    a provision, mount, evaluate, failover, release, or lookup
    operation cannot be performed.
    """

    pass
