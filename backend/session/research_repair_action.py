from dataclasses import (
    dataclass,
    field,
)

from typing import (
    Any,
)

from .research_repair_risk import (
    ResearchRepairRisk,
)


@dataclass
class ResearchRepairAction:
    """
    Represents one proposed response
    to an integrity finding.
    """

    finding_code: str

    action_type: str

    description: str

    risk: (
        ResearchRepairRisk
    )

    entity_type: (
        str | None
    ) = None

    entity_id: (
        str | None
    ) = None

    parameters: dict[
        str,
        Any,
    ] = field(
        default_factory=dict,
    )

    automatic: bool = False

    def to_dict(self):

        return {

            "finding_code":
                self.finding_code,

            "action_type":
                self.action_type,

            "description":
                self.description,

            "risk":
                self.risk.value,

            "entity_type":
                self.entity_type,

            "entity_id":
                self.entity_id,

            "parameters":
                dict(
                    self.parameters
                ),

            "automatic":
                self.automatic,
        }
