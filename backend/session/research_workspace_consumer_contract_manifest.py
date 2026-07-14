from dataclasses import (
    dataclass,
    field,
)

from .research_workspace_consumer_contract_descriptor import (
    ResearchWorkspaceConsumerContractDescriptor,
)

from .research_workspace_consumer_contract_version import (
    ResearchWorkspaceConsumerContractVersion,
)


@dataclass
class ResearchWorkspaceConsumerContractManifest:
    """
    A versioned, machine-readable listing
    of the consumer read contracts exposed
    by the research workspace.
    """

    manifest_version: (
        ResearchWorkspaceConsumerContractVersion
    )

    contracts: list[
        ResearchWorkspaceConsumerContractDescriptor
    ] = field(
        default_factory=list,
    )

    total_count: int = 0

    def to_dict(self):

        return {

            "manifest_version":
                self.manifest_version
                .to_dict(),

            "total_count":
                self.total_count,

            "contracts": [

                descriptor.to_dict()

                for descriptor

                in self.contracts
            ],
        }
