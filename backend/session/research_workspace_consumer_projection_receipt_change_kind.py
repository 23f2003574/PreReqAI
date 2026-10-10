from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionReceiptChangeKind(
    str,
    Enum,
):
    """
    Directional classification of one difference detected
    between two consumer projection execution receipts.

    UNCHANGED means no relevant difference was detected.

    IMPROVED means execution conditions became objectively
    better according to existing receipt semantics.

    DEGRADED means execution conditions became objectively
    worse according to existing receipt semantics.

    CHANGED means a difference exists, but it is not
    inherently better or worse (for example, a semantic
    fingerprint or contract version difference).
    """

    UNCHANGED = (
        "unchanged"
    )

    IMPROVED = (
        "improved"
    )

    DEGRADED = (
        "degraded"
    )

    CHANGED = (
        "changed"
    )
