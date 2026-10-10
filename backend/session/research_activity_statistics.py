from dataclasses import (
    dataclass,
    field,
)


@dataclass
class ResearchActivityStatistics:
    """
    Aggregate research activity counts
    across useful time windows.
    """

    total_events: int

    events_last_24_hours: int

    events_last_7_days: int

    events_last_30_days: int

    counts_by_type: dict[
        str,
        int,
    ] = field(
        default_factory=dict,
    )

    def to_dict(self):

        return {

            "total_events":
                self.total_events,

            "events_last_24_hours":
                self.events_last_24_hours,

            "events_last_7_days":
                self.events_last_7_days,

            "events_last_30_days":
                self.events_last_30_days,

            "counts_by_type":
                dict(
                    self.counts_by_type
                ),
        }
