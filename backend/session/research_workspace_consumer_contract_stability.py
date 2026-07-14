from enum import (
    Enum,
)


class ResearchWorkspaceConsumerContractStability(
    str,
    Enum,
):
    """
    Describes the compatibility maturity
    of a consumer contract.
    """

    EXPERIMENTAL = (
        "experimental"
    )

    STABLE = (
        "stable"
    )

    DEPRECATED = (
        "deprecated"
    )
