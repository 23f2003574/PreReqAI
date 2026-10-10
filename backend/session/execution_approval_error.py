class ExecutionApprovalError(ValueError):
    """
    Raised when an execution approval request is invalid, unknown, or
    a create, approve, reject, pending, or status operation cannot be
    performed.
    """

    pass
