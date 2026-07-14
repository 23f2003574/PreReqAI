from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionReceiptVerificationIssueCode(
    str,
    Enum,
):
    """
    Specific verification issue codes for cross-layer consistency checks.

    Each code identifies a specific type of mismatch between the receipt
    and the finalized execution artifacts from which it was produced.

    The verification layer remains focused and architectural, avoiding
    hundreds of field-specific codes.
    """

    PROJECTION_NAME_MISMATCH = (
        "projection_name_mismatch"
    )

    CONTRACT_VERSION_MISMATCH = (
        "contract_version_mismatch"
    )

    FINGERPRINT_MISMATCH = (
        "fingerprint_mismatch"
    )

    EXECUTION_ID_MISMATCH = (
        "execution_id_mismatch"
    )

    OBSERVATION_TIME_MISMATCH = (
        "observation_time_mismatch"
    )

    DIAGNOSTICS_SUMMARY_MISMATCH = (
        "diagnostics_summary_mismatch"
    )

    FRESHNESS_SUMMARY_MISMATCH = (
        "freshness_summary_mismatch"
    )

    BUDGET_SUMMARY_MISMATCH = (
        "budget_summary_mismatch"
    )

    PROVENANCE_SUMMARY_MISMATCH = (
        "provenance_summary_mismatch"
    )

    EXECUTION_STATUS_MISMATCH = (
        "execution_status_mismatch"
    )
