class ExecutionSecretRotationError(ValueError):
    """
    Raised when an execution secret rotation is invalid, or a
    rotate, lookup, or rollback operation cannot be performed.
    """

    pass
