from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionFreshnessReason(
    str,
    Enum,
):
    """
    Explains why a freshness evaluation
    reached its classification.
    """

    WITHIN_FRESH_WINDOW = (
        "within_fresh_window"
    )

    OUTSIDE_FRESH_WINDOW = (
        "outside_fresh_window"
    )

    OUTSIDE_USABLE_WINDOW = (
        "outside_usable_window"
    )

    SOURCE_TIMESTAMP_IN_FUTURE = (
        "source_timestamp_in_future"
    )
