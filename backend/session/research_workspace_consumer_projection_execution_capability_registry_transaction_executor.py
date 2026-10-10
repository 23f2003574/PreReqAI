from .research_workspace_consumer_projection_execution_capability_registry import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry,
)

from .research_workspace_consumer_projection_execution_capability_registry_transaction import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransaction,
)

from .research_workspace_consumer_projection_execution_capability_registry_transaction_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionError,
)

from .research_workspace_consumer_projection_execution_capability_registry_transaction_operation import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionOperation,
)


REGISTER = (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionOperation
    .REGISTER
)

UPDATE = (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionOperation
    .UPDATE
)

REMOVE = (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionOperation
    .REMOVE
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionExecutor:
    """
    Executes a consumer projection execution capability registry
    transaction atomically, producing a brand-new registry without
    mutating the original.

    The executor's responsibility is applying a set of REGISTER,
    UPDATE, and REMOVE entries as a single unit. It does NOT mutate
    the input registry, mutate the transaction, or mutate any
    decision package. If any entry cannot be applied, the entire
    transaction is aborted and no registry is returned.

    The executor is:
    - Stateless: No instance state
    - Deterministic: Same registry and transaction always produce
      the same result
    - Side-effect free: Never mutates its inputs
    - Atomic: Either every entry applies, or none do
    """

    def execute(

        self,

        registry,

        transaction,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry:
        """
        Apply a transaction against a registry and return a new,
        updated registry.

        Args:
            registry: The existing registry to apply the
                transaction against
            transaction: The transaction describing the entries to
                apply, in order

        Returns:
            A brand-new registry reflecting every entry in the
            transaction

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionError:
                If the registry or transaction is None or the wrong
                type, an entry is malformed, entries conflict, or an
                entry's operation cannot be satisfied
        """

        if registry is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionError(
                    "Cannot execute a transaction against a None "
                    "registry."
                )
            )

        if not isinstance(

            registry,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionError(
                    "Cannot execute transaction: registry must be "
                    "a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry."
                )
            )

        if transaction is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionError(
                    "Cannot execute a None transaction."
                )
            )

        if not isinstance(

            transaction,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransaction,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionError(
                    "Cannot execute transaction: transaction must "
                    "be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransaction."
                )
            )

        seen_projection_names = set()

        for entry in transaction.entries:

            if not isinstance(

                entry.operation,

                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionOperation,
            ):

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionError(
                        "Cannot execute transaction: invalid "
                        f"operation {entry.operation!r}."
                    )
                )

            projection_name = (
                entry.package.projection_name
            )

            if not projection_name:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionError(
                        "Cannot execute transaction: entry has an "
                        "empty projection name."
                    )
                )

            if projection_name in seen_projection_names:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionError(
                        "Cannot execute transaction: conflicting "
                        "operations target the same projection: "
                        f"{projection_name}"
                    )
                )

            seen_projection_names.add(
                projection_name
            )

        working_packages = {

            projection_name:
                registry.get(
                    projection_name
                )

            for projection_name

            in registry.list_projection_names()
        }

        for entry in transaction.entries:

            projection_name = (
                entry.package.projection_name
            )

            if entry.operation == REGISTER:

                if projection_name in working_packages:

                    raise (
                        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionError(
                            "Cannot execute transaction: cannot "
                            f"REGISTER '{projection_name}', it is "
                            "already registered."
                        )
                    )

                working_packages[
                    projection_name
                ] = entry.package

            elif entry.operation == UPDATE:

                if projection_name not in working_packages:

                    raise (
                        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionError(
                            "Cannot execute transaction: cannot "
                            f"UPDATE '{projection_name}', it is "
                            "not registered."
                        )
                    )

                working_packages[
                    projection_name
                ] = entry.package

            elif entry.operation == REMOVE:

                if projection_name not in working_packages:

                    raise (
                        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionError(
                            "Cannot execute transaction: cannot "
                            f"REMOVE '{projection_name}', it is "
                            "not registered."
                        )
                    )

                del working_packages[
                    projection_name
                ]

        updated_registry = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry()
        )

        for projection_name in sorted(
            working_packages
        ):

            updated_registry.register(
                working_packages[
                    projection_name
                ]
            )

        return updated_registry
