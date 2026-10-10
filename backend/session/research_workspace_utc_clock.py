from datetime import (
    datetime,
    timezone,
)


class ResearchWorkspaceUtcClock:
    """
    Wall-clock source of timezone-aware
    UTC timestamps, used to compare
    against source data timestamps for
    freshness evaluation. Distinct from
    the monotonic clock used for duration
    measurement.
    """

    def now(self):

        return datetime.now(
            timezone.utc
        )
