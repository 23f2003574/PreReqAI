from .research_workspace_consumer_projection_execution_capability_registry import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry,
)

from .research_workspace_consumer_projection_execution_capability_registry_transaction_coordinator_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionCoordinatorError,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionCoordinator:
    """
    Orchestrates validation and execution of a consumer projection
    execution capability registry transaction, enforcing an
    all-or-nothing workflow.

    The coordinator owns orchestration only - it does NOT validate
    transaction contents, execute registry operations, repair
    invalid transactions, or modify transaction entries. Those
    responsibilities belong to the injected validator and executor.

    The coordinator is:
    - Stateless: Holds only the two collaborators it was given
    - Deterministic: Same registry and transaction always produce
      the same outcome
    - Side-effect free: Never mutates its inputs itself
    """

    def __init__(

        self,

        validator,

        executor,

    ):

        self._validator = validator

        self._executor = executor

    def coordinate(

        self,

        registry,

        transaction,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry:
        """
        Validate a transaction and, only if it is valid, execute it
        against a registry.

        Args:
            registry: The existing registry to apply the
                transaction against
            transaction: The transaction to validate and execute

        Returns:
            A brand-new registry reflecting the executed
            transaction

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionCoordinatorError:
                If the transaction fails validation. The executor is
                never invoked in this case.
        """

        validation_report = (

            self._validator.validate(
                transaction
            )
        )

        if not validation_report.is_valid:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionCoordinatorError(
                    "Cannot coordinate transaction: validation "
                    "failed (unsafe projection names: "
                    f"{validation_report.duplicate_projection_names})."
                )
            )

        return (
            self._executor.execute(
                registry,

                transaction,
            )
        )
