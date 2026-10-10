from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionQualitySignalCode(
    str,
    Enum,
):
    """
    Compact vocabulary of consumer-relevant execution conditions
    that can be extracted from a finalized execution receipt.

    Each code identifies one explicit fact already present in the
    receipt - not a newly computed judgment. The vocabulary stays
    deliberately small rather than growing one code per receipt field.
    """

    EXECUTION_DEGRADED = (
        "execution_degraded"
    )

    STALE_DATA_USED = (
        "stale_data_used"
    )

    EXPIRED_DATA_PRESENT = (
        "expired_data_present"
    )

    UNKNOWN_FRESHNESS_PRESENT = (
        "unknown_freshness_present"
    )

    BUDGET_EXHAUSTED = (
        "budget_exhausted"
    )

    OPTIONAL_WORK_SKIPPED = (
        "optional_work_skipped"
    )

    INCOMPLETE_PROVENANCE = (
        "incomplete_provenance"
    )
