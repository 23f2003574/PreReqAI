from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionProvenanceNodeKind(
    str,
    Enum,
):
    """
    Distinguishes the three roles a
    provenance graph node can play.
    """

    SOURCE = (
        "source"
    )

    DERIVATION = (
        "derivation"
    )

    OUTPUT = (
        "output"
    )
