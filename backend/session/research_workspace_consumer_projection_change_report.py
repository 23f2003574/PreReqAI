from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_change_status import (
    ResearchWorkspaceConsumerProjectionChangeStatus,
)

from .research_workspace_consumer_projection_fingerprint_snapshot import (
    ResearchWorkspaceConsumerProjectionFingerprintSnapshot,
)

from .research_workspace_consumer_projection_section_change import (
    ResearchWorkspaceConsumerProjectionSectionChange,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionChangeReport:
    """
    Immutable report detailing the semantic changes
    detected when comparing two consumer projection
    fingerprint snapshots.

    The report identifies:
    - The projection type
    - Overall change status (unchanged, changed, or incomparable)
    - Previous snapshot
    - Current snapshot
    - Section-level changes (if comparable)

    This report answers:
    - Did the consumer-facing state change?
    - If so, which logical sections changed?

    The report remains compact and deterministic,
    enabling efficient change detection and
    selective UI refresh strategies.

    Attributes:
        projection_name: The projection identifier
        status: Overall change status
        previous: The previous fingerprint snapshot
        current: The current fingerprint snapshot
        section_changes: Immutable tuple of section changes,
                        sorted by section name
    """

    projection_name: str

    status: (
        ResearchWorkspaceConsumerProjectionChangeStatus
    )

    previous: (
        ResearchWorkspaceConsumerProjectionFingerprintSnapshot
    )

    current: (
        ResearchWorkspaceConsumerProjectionFingerprintSnapshot
    )

    section_changes: (
        tuple[
            ResearchWorkspaceConsumerProjectionSectionChange,
            ...
        ]
    ) = ()
