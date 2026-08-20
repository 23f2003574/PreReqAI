class ExecutionArtifactGarbageCollectionError(ValueError):
    """
    Raised when an execution artifact garbage record is invalid,
    unknown, or a scan, mark, collect, protection-check, or history
    operation cannot be performed.
    """

    pass
