from dataclasses import (
    dataclass,
)


@dataclass
class ResearchWorkspaceConsumerProjectionOutputProvenance:
    """
    Identifies one logical consumer-
    facing result by its stable,
    semantic output identity.
    """

    node_id: str

    output_type: str

    output_key: str

    def to_dict(self):

        return {

            "node_id":
                self.node_id,

            "output_type":
                self.output_type,

            "output_key":
                self.output_key,
        }
