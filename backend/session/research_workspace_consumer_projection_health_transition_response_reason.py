from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionHealthTransitionResponseReason(
    str,
    Enum,
):
    """
    Compact reason code for a Commit #10 response directive, mapped
    directly from the Commit #7 operational assessment vocabulary.

    This stays at the operational level - it does not enumerate
    individual quality signals. Detailed signal-level evidence
    remains owned by Commit #5's transition explanation.
    """

    HEALTH_STABLE = (
        "health_stable"
    )

    CONDITIONS_IMPROVING = (
        "conditions_improving"
    )

    HEALTH_RECOVERED = (
        "health_recovered"
    )

    MIXED_CHANGES = (
        "mixed_changes"
    )

    HEALTH_DETERIORATING = (
        "health_deteriorating"
    )

    HEALTH_ESCALATED = (
        "health_escalated"
    )
