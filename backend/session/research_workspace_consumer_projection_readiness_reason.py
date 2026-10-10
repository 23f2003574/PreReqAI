from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionReadinessReason(
    str,
    Enum,
):
    """
    A generic, standardized primary cause for a
    projection readiness classification.
    """

    ALL_REQUIREMENTS_MET = (
        "all_requirements_met"
    )

    OPTIONAL_CONSTRAINTS_PRESENT = (
        "optional_constraints_present"
    )

    REQUIRED_DEPENDENCY_MISSING = (
        "required_dependency_missing"
    )

    REQUIRED_SOURCE_UNAVAILABLE = (
        "required_source_unavailable"
    )

    EXECUTION_DISABLED = (
        "execution_disabled"
    )

    BUDGET_EXHAUSTED = (
        "budget_exhausted"
    )
