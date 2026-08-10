class ExecutionArtifactPrefetchError(ValueError):
    """
    Raised when an execution artifact prefetch is invalid, unknown,
    or cannot be scheduled, executed, cancelled, or looked up.
    """

    pass
