class ExecutionChangeRequestError(ValueError):
    """
    Raised when an execution change request is invalid, unknown, or a
    create, approve, reject, apply, or status operation cannot be
    performed.
    """

    pass
