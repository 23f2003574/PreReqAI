class ExecutionSecretLeaseError(ValueError):
    """
    Raised when an execution secret lease is invalid, unknown, or
    cannot be acquired, renewed, released, or cleaned up.
    """

    pass
