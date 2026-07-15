class ResearchWorkspaceConsumerProjectionReceiptComparisonError(
    ValueError
):
    """
    Raised when two consumer projection execution receipts
    cannot be directly compared.

    Receipts can only be compared when they describe the same
    logical projection. Comparing receipts for unrelated
    projections would produce a meaningless result, so this
    error is raised instead of silently comparing them.
    """

    pass
