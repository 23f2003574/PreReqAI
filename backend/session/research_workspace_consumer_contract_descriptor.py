from dataclasses import (
    dataclass,
    field,
)

from .research_workspace_capability import (
    ResearchWorkspaceCapability,
)

from .research_workspace_consumer_contract_id import (
    ResearchWorkspaceConsumerContractId,
)

from .research_workspace_consumer_contract_parameter import (
    ResearchWorkspaceConsumerContractParameter,
)

from .research_workspace_consumer_contract_scope import (
    ResearchWorkspaceConsumerContractScope,
)

from .research_workspace_consumer_contract_stability import (
    ResearchWorkspaceConsumerContractStability,
)

from .research_workspace_consumer_contract_version import (
    ResearchWorkspaceConsumerContractVersion,
)


@dataclass
class ResearchWorkspaceConsumerContractDescriptor:
    """
    Describes one stable, transport-
    independent consumer read contract.
    """

    contract_id: (
        ResearchWorkspaceConsumerContractId
    )

    version: (
        ResearchWorkspaceConsumerContractVersion
    )

    scope: (
        ResearchWorkspaceConsumerContractScope
    )

    stability: (
        ResearchWorkspaceConsumerContractStability
    )

    description: str

    projection_name: str

    read_only: bool

    parameters: list[
        ResearchWorkspaceConsumerContractParameter
    ] = field(
        default_factory=list,
    )

    required_capabilities: list[
        ResearchWorkspaceCapability
    ] = field(
        default_factory=list,
    )

    def to_dict(self):

        return {

            "contract_id":
                self.contract_id.value,

            "version":
                self.version.to_dict(),

            "scope":
                self.scope.value,

            "stability":
                self.stability.value,

            "description":
                self.description,

            "projection_name":
                self.projection_name,

            "read_only":
                self.read_only,

            "parameters": [

                parameter.to_dict()

                for parameter

                in self.parameters
            ],

            "required_capabilities": [

                capability.value

                for capability

                in self.required_capabilities
            ],
        }
