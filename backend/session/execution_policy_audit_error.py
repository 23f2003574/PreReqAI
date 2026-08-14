class ExecutionPolicyAuditError(ValueError):
    """
    Raised when an execution policy audit event is invalid, or a
    record, history, policy_history, latest, or purge operation
    cannot be performed.
    """

    pass
