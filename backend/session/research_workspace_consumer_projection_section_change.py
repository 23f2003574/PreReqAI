from dataclasses import (
    dataclass,
)

from typing import (
    Optional,
)

from .research_workspace_consumer_projection_fingerprint import (
    ResearchWorkspaceConsumerProjectionFingerprint,
)

from .research_workspace_consumer_projection_section_change_status import (
    ResearchWorkspaceConsumerProjectionSectionChangeStatus,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionSectionChange:
    """
    Captures the detected change (or lack thereof)
    in one logical section of a consumer projection
    between two fingerprint snapshots.

    Attributes:
        section_name: The stable logical section identifier
        status: Whether the section was unchanged, changed, added, or removed
        previous_fingerprint: The section fingerprint from the previous snapshot
                             (None if the section was added)
        current_fingerprint: The section fingerprint from the current snapshot
                            (None if the section was removed)
    """

    section_name: str

    status: (
        ResearchWorkspaceConsumerProjectionSectionChangeStatus
    )

    previous_fingerprint: (
        Optional[
            ResearchWorkspaceConsumerProjectionFingerprint
        ]
    ) = None

    current_fingerprint: (
        Optional[
            ResearchWorkspaceConsumerProjectionFingerprint
        ]
    ) = None
