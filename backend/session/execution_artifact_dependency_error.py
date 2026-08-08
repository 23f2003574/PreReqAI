class ExecutionArtifactDependencyError(ValueError):
    """
    Raised when an execution artifact dependency is invalid, unknown,
    self-referential, or would introduce a dependency cycle.
    """

    pass
