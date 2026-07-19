from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_decision_package import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionPackage,
)

from .research_workspace_consumer_projection_execution_capability_registry_transaction_operation import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionOperation,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionEntry:
    """
    One immutable unit of change within a consumer projection
    execution capability registry transaction.

    Attributes:
        operation: The kind of change this entry applies
        package: The decision package the entry operates on - for
            REGISTER and UPDATE, the package to store; for REMOVE,
            the package identifying the projection to remove
    """

    operation: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionOperation
    )

    package: (
        ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionPackage
    )
