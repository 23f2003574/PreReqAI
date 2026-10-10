from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_fingerprint import (
    ResearchWorkspaceConsumerProjectionFingerprint,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionSectionFingerprint:
    """
    Represents the deterministic semantic identity
    of one logical section within a consumer projection.

    For example, a bootstrap projection may have sections:
    - readiness
    - attention
    - actions
    - insights
    - recent_activity

    Each section has its own stable fingerprint,
    enabling section-level change detection.

    Attributes:
        section_name: The stable logical section identifier
        fingerprint: The semantic fingerprint of that section
    """

    section_name: str

    fingerprint: (
        ResearchWorkspaceConsumerProjectionFingerprint
    )
