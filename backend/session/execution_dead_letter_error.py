class ExecutionDeadLetterError(ValueError):
    """
    Raised when an execution dead-letter job is invalid, unknown, or
    a move, retry, or discard operation cannot be performed.
    """

    pass
