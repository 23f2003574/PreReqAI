from dataclasses import (
    dataclass,
)


@dataclass
class ResearchWorkspaceConsumerContractVersion:
    """
    Represents an explicit major/minor
    compatibility version for one consumer
    contract or the manifest itself.
    """

    major: int

    minor: int

    def __post_init__(self):

        if self.major < 0:

            raise ValueError(

                "Consumer contract version "
                "major cannot be negative"
            )

        if self.minor < 0:

            raise ValueError(

                "Consumer contract version "
                "minor cannot be negative"
            )

    def to_dict(self):

        return {

            "major":
                self.major,

            "minor":
                self.minor,
        }
