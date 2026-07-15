from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationKind(
    str,
    Enum,
):
    """
    Generic recommended response posture for a Commit #7 operational
    assessment.

    NO_ACTION means no response is currently required.

    CONTINUE_OBSERVATION means conditions are improving but should
    continue to be observed.

    REVIEW_CHANGES means mixed changes warrant inspection.

    INVESTIGATE means deterioration should be investigated.

    PRIORITIZE_REVIEW means critical escalation should receive
    prioritized human or system review.

    This vocabulary stays generic - it defines a response posture,
    not a remediation procedure. No application-specific action
    (e.g. "refresh source X", "increase budget") is encoded here.
    """

    NO_ACTION = (
        "no_action"
    )

    CONTINUE_OBSERVATION = (
        "continue_observation"
    )

    REVIEW_CHANGES = (
        "review_changes"
    )

    INVESTIGATE = (
        "investigate"
    )

    PRIORITIZE_REVIEW = (
        "prioritize_review"
    )
