class ExecutionStorageQuotaError(ValueError):
    """
    Raised when an execution storage quota is invalid, unknown, or a
    configure, allocate, release, or lookup operation cannot be
    performed.
    """

    pass
