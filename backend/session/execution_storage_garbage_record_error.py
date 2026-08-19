class ExecutionStorageGarbageRecordError(ValueError):
    """
    Raised when an execution storage garbage record is invalid,
    unknown, or a scan, mark, collect, or lookup operation cannot be
    performed.
    """

    pass
