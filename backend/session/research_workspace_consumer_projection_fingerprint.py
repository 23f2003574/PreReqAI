from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_fingerprint_algorithm import (
    ResearchWorkspaceConsumerProjectionFingerprintAlgorithm,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionFingerprint:
    """
    Represents a stable deterministic semantic identity
    for consumer-meaningful projection content.

    A fingerprint encodes:
    - Which algorithm was used (e.g., SHA-256)
    - The computed digest value (lowercase hex)

    The fingerprint identifies consumer-meaningful state,
    not execution incidentals such as:
    - Request timestamps
    - Diagnostics metadata
    - Provenance node IDs
    - Execution duration

    Two projections with the same semantic consumer state
    must produce identical fingerprints.

    Attributes:
        algorithm: The fingerprinting algorithm used
        value: The computed digest (lowercase hexadecimal)
    """

    algorithm: (
        ResearchWorkspaceConsumerProjectionFingerprintAlgorithm
    )

    value: str
