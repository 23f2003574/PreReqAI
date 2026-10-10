from dataclasses import (
    dataclass,
    field,
)


@dataclass
class ResearchLifecycleStatistics:
    """
    Counts research sessions by
    lifecycle status.
    """

    counts: dict[
        str,
        int,
    ] = field(
        default_factory=dict,
    )

    def count_for(

        self,

        status,

    ) -> int:

        value = (

            status.value

            if hasattr(
                status,
                "value",
            )

            else str(
                status
            )
        )

        return self.counts.get(

            value,

            0,
        )

    def to_dict(self):

        return {

            "counts":
                dict(
                    self.counts
                )
        }
