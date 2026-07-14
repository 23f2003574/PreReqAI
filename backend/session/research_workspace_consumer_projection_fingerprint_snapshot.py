from dataclasses import (
    dataclass,
)

from typing import (
    Optional,
)

from .research_workspace_consumer_projection_fingerprint import (
    ResearchWorkspaceConsumerProjectionFingerprint,
)

from .research_workspace_consumer_projection_section_fingerprint import (
    ResearchWorkspaceConsumerProjectionSectionFingerprint,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionFingerprintSnapshot:
    """
    Immutable snapshot of the semantic identity
    of one consumer projection at one point in time.

    A snapshot captures:
    - Which projection was fingerprinted
    - Which contract version was active
    - The overall fingerprint of all semantic state
    - The individual section fingerprints

    This snapshot can be used for:
    - Comparing two projection states
    - Identifying which sections changed
    - Verifying semantic equivalence

    The snapshot itself is:
    - Immutable
    - Deterministic
    - Compact (not including the full projection payload)

    Attributes:
        projection_name: Stable identifier for this projection type
        contract_version: Optional contract version active at fingerprint time
        overall: The comprehensive semantic fingerprint
        sections: Immutable tuple of section fingerprints, sorted by name
    """

    projection_name: str

    contract_version: (
        Optional[str]
    ) = None

    overall: (
        ResearchWorkspaceConsumerProjectionFingerprint
    ) = None

    sections: (
        tuple[
            ResearchWorkspaceConsumerProjectionSectionFingerprint,
            ...
        ]
    ) = ()
