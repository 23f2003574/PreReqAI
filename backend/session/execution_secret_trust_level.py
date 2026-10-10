from enum import Enum


class ExecutionSecretTrustLevel(
    str,
    Enum,
):
    """
    Defines how much a principal is trusted to access execution
    secrets, ranked from least to most trusted: LOW, STANDARD, HIGH.
    """

    LOW = "low"

    STANDARD = "standard"

    HIGH = "high"
