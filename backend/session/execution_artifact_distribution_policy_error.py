class ExecutionArtifactDistributionPolicyError(ValueError):
    """
    Raised when an execution artifact distribution policy or its
    assignment is invalid, unknown, or an artifact fails to validate
    against a channel's active policy.
    """

    pass
