from enum import (
    Enum,
)


class ResearchWorkspaceConsumerProjectionReceiptVerificationStatus(
    str,
    Enum,
):
    """
    Status of receipt verification against finalized execution artifacts.

    VERIFIED means the receipt accurately describes the execution artifacts.
    INVALID means one or more cross-layer consistency mismatches were detected.

    The verification layer checks internal architectural consistency,
    not cryptographic authenticity or non-repudiation.
    """

    VERIFIED = (
        "verified"
    )

    INVALID = (
        "invalid"
    )
