from dataclasses import (
    dataclass,
)


@dataclass
class ResearchWorkspaceConsumerProjectionDerivationProvenance:
    """
    Identifies one explicit, semantically
    named projection rule that
    transformed evidence into another
    result.
    """

    node_id: str

    rule_name: str

    def to_dict(self):

        return {

            "node_id":
                self.node_id,

            "rule_name":
                self.rule_name,
        }
