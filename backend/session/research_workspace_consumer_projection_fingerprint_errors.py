class ResearchWorkspaceConsumerProjectionFingerprintError(
    Exception,
):
    """
    Base error for consumer projection fingerprinting failures.
    """

    pass


class ResearchWorkspaceUnsupportedCanonicalValueError(
    ResearchWorkspaceConsumerProjectionFingerprintError,
):
    """
    Raised when a value cannot be canonicalized
    to a deterministic primitive representation.

    This should never silently fall back to
    arbitrary hashing. Clear failure is better.
    """

    pass


class ResearchWorkspaceNaiveDatetimeCanonicalizationError(
    ResearchWorkspaceConsumerProjectionFingerprintError,
):
    """
    Raised when a naive (timezone-unaware) datetime
    is encountered during canonicalization.

    To ensure stable fingerprints across timezones
    and process restarts, all datetimes must be
    explicitly timezone-aware in UTC.
    """

    pass


class ResearchWorkspaceProjectionFingerprintPolicyNotFoundError(
    ResearchWorkspaceConsumerProjectionFingerprintError,
):
    """
    Raised when attempting to fingerprint a projection
    without a registered fingerprinting policy.
    """

    pass


class ResearchWorkspaceIncomparableProjectionSnapshotsError(
    ResearchWorkspaceConsumerProjectionFingerprintError,
):
    """
    Raised when attempting to compare projection snapshots
    that cannot be meaningfully compared due to
    incompatible projection types or versions.
    """

    pass
