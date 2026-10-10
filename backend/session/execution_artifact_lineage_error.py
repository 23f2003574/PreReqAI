class ExecutionArtifactLineageError(ValueError):
    """
    Raised when execution artifact lineage is invalid, unknown,
    self-referential, or refers to a version that does not exist.
    """

    pass
