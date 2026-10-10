from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_contract_parameter_type import (
    ResearchWorkspaceConsumerContractParameterType,
)


@dataclass
class ResearchWorkspaceConsumerContractParameter:
    """
    Describes one logical input accepted
    by a consumer contract.
    """

    name: str

    required: bool

    value_type: (
        ResearchWorkspaceConsumerContractParameterType
    )

    description: str

    def to_dict(self):

        return {

            "name":
                self.name,

            "required":
                self.required,

            "value_type":
                self.value_type.value,

            "description":
                self.description,
        }
