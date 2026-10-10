from enum import Enum


class ResearchWorkspaceConsumerProjectionFingerprintAlgorithm(
    str,
    Enum,
):
    """
    Enumeration of supported algorithms for
    deterministic consumer projection fingerprinting.

    The fingerprint algorithm identifies the hashing
    strategy used to produce a stable deterministic
    semantic projection identity.
    """

    SHA256 = "sha256"
