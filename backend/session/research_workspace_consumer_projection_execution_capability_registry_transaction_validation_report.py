from dataclasses import (
    dataclass,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryTransactionValidationReport:
    """
    Immutable, consumer-facing summary of a consumer projection
    execution capability registry transaction integrity check.

    Captures state only - it does not write logs or persist data.

    Attributes:
        total_operations: The number of entries inspected
        register_operations: The number of REGISTER entries
        update_operations: The number of UPDATE entries
        remove_operations: The number of REMOVE entries
        duplicate_projection_names: Projection names that are
            unsafe to apply - because they appear more than once
            within the transaction, because the projection name
            itself is empty, or because the entry's operation or
            package failed validation
        is_valid: True when duplicate_projection_names is empty
    """

    total_operations: int

    register_operations: int

    update_operations: int

    remove_operations: int

    duplicate_projection_names: tuple[
        str,
        ...,
    ]

    is_valid: bool

    def to_dict(self):
        return {
            "total_operations": self.total_operations,
            "register_operations": self.register_operations,
            "update_operations": self.update_operations,
            "remove_operations": self.remove_operations,
            "duplicate_projection_names": list(
                self.duplicate_projection_names
            ),
            "is_valid": self.is_valid,
        }
