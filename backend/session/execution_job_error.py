class ExecutionJobError(ValueError):
    """
    Raised when an execution job is invalid, unknown, or an enqueue,
    dequeue, or cancel operation cannot be performed.
    """

    pass
