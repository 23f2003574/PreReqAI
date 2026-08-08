class ExecutionArtifactBundlePromotionError(ValueError):
    """
    Raised when a bundle promotion is invalid, unknown, cannot be
    completed atomically, or cannot be rolled back.
    """

    pass
