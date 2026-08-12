class ExecutionSecretTokenRotationError(ValueError):
    """
    Raised when an execution secret token rotation is invalid, or a
    rotate, lookup, or revoke_previous operation cannot be performed.
    """

    pass
