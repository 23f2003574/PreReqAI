from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_contract_version import (
    ResearchWorkspaceConsumerContractVersion,
)


@dataclass
class ResearchWorkspaceConsumerContractCompatibility:
    """
    Represents the result of comparing a
    consumer's requested contract version
    against the currently available one.
    """

    contract_id: str

    requested_version: (
        ResearchWorkspaceConsumerContractVersion
    )

    available_version: (
        ResearchWorkspaceConsumerContractVersion
        | None
    )

    compatible: bool

    reason: (
        str | None
    )

    def to_dict(self):

        return {

            "contract_id":
                self.contract_id,

            "requested_version":
                self.requested_version
                .to_dict(),

            "available_version": (

                self.available_version
                .to_dict()

                if self.available_version

                is not None

                else None
            ),

            "compatible":
                self.compatible,

            "reason":
                self.reason,
        }
