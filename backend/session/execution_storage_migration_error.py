class ExecutionStorageMigrationError(ValueError):
    """
    Raised when an execution storage migration is invalid, unknown,
    or a start, verify, complete, rollback, or lookup operation
    cannot be performed.
    """

    pass
