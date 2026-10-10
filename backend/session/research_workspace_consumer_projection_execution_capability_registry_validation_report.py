from dataclasses import (
    dataclass,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryValidationReport:
    """
    Immutable, consumer-facing summary of a consumer projection
    execution capability registry integrity check.

    Captures state only - it does not write logs or persist data.

    Attributes:
        total_packages: The number of packages inspected
        valid_packages: The number of packages that passed
            validation
        invalid_packages: The number of packages that failed
            validation
        is_valid: True when every inspected package is valid
    """

    total_packages: int

    valid_packages: int

    invalid_packages: int

    is_valid: bool

    def to_dict(self):
        return {
            "total_packages": self.total_packages,
            "valid_packages": self.valid_packages,
            "invalid_packages": self.invalid_packages,
            "is_valid": self.is_valid,
        }
