class ResearchWorkspaceConsumerProjectionFreshnessPolicyNotFoundError(
    Exception
):
    """
    Raised when freshness evaluation is
    requested for a source with no
    registered freshness policy. A
    configuration problem, distinct from
    an UNUSABLE evaluation result.
    """

    def __init__(

        self,

        source_name,

    ):

        self.source_name = (
            source_name
        )

        super().__init__(

            "No freshness policy "
            f"registered for source "
            f"'{source_name}'"
        )
