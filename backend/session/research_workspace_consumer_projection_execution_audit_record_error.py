class ResearchWorkspaceConsumerProjectionExecutionAuditRecordError(
    ValueError
):
    """
    Raised when an execution snapshot cannot be composed into an
    execution audit record.

    The snapshot's projection name must be non-empty. Composing a
    record with no identifiable projection would produce a
    meaningless audit artifact, so this error is raised instead of
    silently composing it.
    """

    pass
