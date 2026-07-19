from .research_workspace_consumer_projection_execution_capability_decision import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision,
)

from .research_workspace_consumer_projection_execution_capability_registry_transaction import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransaction,
)

from .research_workspace_consumer_projection_execution_capability_registry_transaction_operation import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionOperation,
)

from .research_workspace_consumer_projection_execution_capability_registry_transaction_validation_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionValidationError,
)

from .research_workspace_consumer_projection_execution_capability_registry_transaction_validation_report import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionValidationReport,
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


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionValidator:
    """
    Inspects a consumer projection execution capability registry
    transaction for integrity before it is handed to a transaction
    executor.

    The validator's responsibility is inspection, not repair. It
    does NOT modify entries, reorder operations, remove duplicates,
    or repair invalid data.

    The validator is:
    - Stateless: No instance state
    - Deterministic: Same transaction always produces the same
      report
    - Side-effect free: Never mutates the transaction or its
      entries
    """

    def validate(

        self,

        transaction,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionValidationReport:
        """
        Validate the integrity of a consumer projection execution
        capability registry transaction.

        Args:
            transaction: The transaction to validate

        Returns:
            An immutable validation report summarizing the
            transaction's operation counts and any unsafe
            projection names

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionValidationError:
                If the transaction is None, is not a transaction, or
                contains an entry that cannot be inspected
        """

        if transaction is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionValidationError(
                    "Cannot validate a None transaction."
                )
            )

        if not isinstance(

            transaction,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransaction,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionValidationError(
                    "Cannot validate transaction: transaction "
                    "must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransaction."
                )
            )

        total_operations = 0

        register_operations = 0

        update_operations = 0

        remove_operations = 0

        name_counts = {}

        problem_names = set()

        for entry in transaction.entries:

            try:

                operation = (
                    entry.operation
                )

                package = (
                    entry.package
                )

                projection_name = (
                    package.projection_name
                )

                decision = (
                    package.decision
                )

                executable = (
                    package.executable
                )

                title = (
                    package.title
                )

                message = (
                    package.message
                )

            except AttributeError as error:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionValidationError(
                        "Cannot validate transaction: an entry "
                        "cannot be inspected as a transaction "
                        f"entry ({error})."
                    )
                ) from error

            total_operations += 1

            if operation == REGISTER:

                register_operations += 1

            elif operation == UPDATE:

                update_operations += 1

            elif operation == REMOVE:

                remove_operations += 1

            is_valid_entry = (

                isinstance(

                    operation,

                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionOperation,
                )

                and isinstance(
                    projection_name,

                    str,
                )

                and bool(
                    projection_name
                )

                and isinstance(

                    decision,

                    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision,
                )

                and isinstance(
                    executable,

                    bool,
                )

                and isinstance(
                    title,

                    str,
                )

                and bool(
                    title
                )

                and isinstance(
                    message,

                    str,
                )

                and bool(
                    message
                )
            )

            marker = (

                projection_name

                if isinstance(

                    projection_name,

                    str,
                )

                else ""
            )

            name_counts[marker] = (

                name_counts.get(
                    marker,

                    0,
                )

                + 1
            )

            if not is_valid_entry:

                problem_names.add(
                    marker
                )

        duplicate_names = {

            name

            for name, count

            in name_counts.items()

            if count > 1
        }

        duplicate_projection_names = tuple(

            sorted(

                duplicate_names

                | problem_names
            )
        )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionValidationReport(

                total_operations=total_operations,

                register_operations=register_operations,

                update_operations=update_operations,

                remove_operations=remove_operations,

                duplicate_projection_names=duplicate_projection_names,

                is_valid=(
                    len(duplicate_projection_names) == 0
                ),
            )
        )
