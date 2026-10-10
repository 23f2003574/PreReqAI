from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind(
    str,
    Enum,
):
    """
    Compact operational assessment combining a Commit #4 health
    transition with a Commit #6 transition impact summary.

    STABLE means no meaningful transition-level change.

    IMPROVING means execution conditions improved, but full
    recovery was not reached.

    RECOVERED means execution health returned to HEALTHY.

    DETERIORATING means execution conditions worsened.

    ESCALATED means the execution newly entered CRITICAL health.

    MIXED means positive and negative signal-level changes coexist
    without a cleaner directional assessment.
    """

    STABLE = (
        "stable"
    )

    IMPROVING = (
        "improving"
    )

    RECOVERED = (
        "recovered"
    )

    DETERIORATING = (
        "deteriorating"
    )

    ESCALATED = (
        "escalated"
    )

    MIXED = (
        "mixed"
    )
