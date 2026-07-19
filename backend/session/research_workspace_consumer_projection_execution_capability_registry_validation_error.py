class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryValidationError(
    ValueError
):
    """
    Raised when a consumer projection execution capability registry
    cannot be validated at all.

    This occurs when the registry itself is missing or when a
    stored entry is malformed beyond inspection (for example, it
    lacks the fields a decision package is expected to expose).
    Ordinary validation failures - an empty title, an invalid
    decision value - are reflected in the validation report instead
    of raising this error.
    """

    pass
