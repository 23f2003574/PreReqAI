class ExecutionArtifactReleaseChannelError(ValueError):
    """
    Raised when an execution artifact release channel entry is
    invalid, unknown, or a release, promote, rollback, or lookup
    operation cannot be performed.
    """

    pass
