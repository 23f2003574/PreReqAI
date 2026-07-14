from dataclasses import (
    dataclass,
)


@dataclass
class ResearchWorkspaceConsumerProjectionFreshnessPolicy:
    """
    Declares how old one freshness-aware
    source's data may be before it is
    considered stale, and before it
    becomes unusable.
    """

    source_name: str

    fresh_for_ms: float

    usable_for_ms: float

    def __post_init__(self):

        if self.fresh_for_ms < 0:

            raise ValueError(

                "Freshness policy fresh_for_ms "
                "cannot be negative"
            )

        if self.usable_for_ms < 0:

            raise ValueError(

                "Freshness policy "
                "usable_for_ms cannot be "
                "negative"
            )

        if (

            self.usable_for_ms

            < self.fresh_for_ms
        ):

            raise ValueError(

                "Freshness policy "
                "usable_for_ms cannot be "
                "shorter than fresh_for_ms"
            )

    def to_dict(self):

        return {

            "source_name":
                self.source_name,

            "fresh_for_ms":
                self.fresh_for_ms,

            "usable_for_ms":
                self.usable_for_ms,
        }
