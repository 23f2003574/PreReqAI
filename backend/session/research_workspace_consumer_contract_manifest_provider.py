from .research_workspace_consumer_contract_manifest import (
    ResearchWorkspaceConsumerContractManifest,
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


_MANIFEST_VERSION = (

    ResearchWorkspaceConsumerContractVersion(

        major=1,

        minor=0,
    )
)


class ResearchWorkspaceConsumerContractManifestProvider:
    """
    Produces the versioned consumer
    contract manifest from the contract
    registry's static structural metadata.
    """

    def __init__(

        self,

        contract_registry,

    ):

        self.contract_registry = (
            contract_registry
        )

    def get_manifest(

        self,

        *,

        scope=None,

        stability=None,

    ):

        contracts = (

            self.contract_registry
            .list_contracts()
        )

        if scope is not None:

            normalized_scope = (

                scope.value

                if isinstance(

                    scope,

                    ResearchWorkspaceConsumerContractScope,
                )

                else scope
            )

            contracts = [

                descriptor

                for descriptor

                in contracts

                if (

                    descriptor.scope.value

                    == normalized_scope
                )
            ]

        if stability is not None:

            normalized_stability = (

                stability.value

                if isinstance(

                    stability,

                    ResearchWorkspaceConsumerContractStability,
                )

                else stability
            )

            contracts = [

                descriptor

                for descriptor

                in contracts

                if (

                    descriptor.stability.value

                    == normalized_stability
                )
            ]

        return (

            ResearchWorkspaceConsumerContractManifest(

                manifest_version=(
                    _MANIFEST_VERSION
                ),

                contracts=contracts,

                total_count=len(
                    contracts
                ),
            )
        )
