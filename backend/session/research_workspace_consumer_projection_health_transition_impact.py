from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionHealthTransitionImpact(
    str,
    Enum,
):
    """
    Directional classification of signal-level change between two
    consumer projection health transition explanations.

    NONE means no signal-level changes occurred (persistent signals
    with no severity change do not count).

    POSITIVE means concerns were resolved or reduced without any
    new concerns or escalations.

    NEGATIVE means new concerns appeared or existing concerns
    escalated without any offsetting improvement.

    MIXED means both positive and negative changes occurred.

    This is not a health score - it classifies signal-level change
    direction, which can differ from the overall health transition
    kind (Commit #4). A health transition can be UNCHANGED while the
    underlying signals shifted (one concern resolved, a different
    one appeared) - that combination is MIXED impact.
    """

    NONE = (
        "none"
    )

    POSITIVE = (
        "positive"
    )

    NEGATIVE = (
        "negative"
    )

    MIXED = (
        "mixed"
    )
