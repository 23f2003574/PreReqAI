class ExecutionBackpressureError(ValueError):
    """
    Raised when an execution backpressure state is invalid, unknown,
    or a configure, enqueue, or dequeue operation cannot be
    performed.
    """

    pass
