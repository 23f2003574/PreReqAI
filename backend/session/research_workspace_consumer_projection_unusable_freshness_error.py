class ResearchWorkspaceConsumerProjectionUnusableFreshnessError(
    Exception
):
    """
    Raised when a source resolved
    successfully but its data is too old
    to trust under its freshness policy.
    Distinct from a resolver failure —
    the underlying read succeeded; the
    freshness policy rejected the result.
    """

    def __init__(

        self,

        *,

        source_name,

        evaluation,

    ):

        self.source_name = (
            source_name
        )

        self.evaluation = (
            evaluation
        )

        super().__init__(

            f"Source '{source_name}' "
            "freshness is unusable "
            f"({evaluation.reason.value})"
        )
