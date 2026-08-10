class ExecutionArtifactRetrievalError(ValueError):
    """
    Raised when an execution artifact retrieval request or result is
    invalid, or a retrieval cannot be completed because the artifact
    or version is unknown or the consumer is not authorized.
    """

    pass
