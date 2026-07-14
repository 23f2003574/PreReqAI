from dataclasses import (
    dataclass,
)

from typing import (
    Optional,
)

from .research_workspace_consumer_projection_fingerprint import (
    ResearchWorkspaceConsumerProjectionFingerprint,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionIdentity:
    """
    Compact identity of one consumer projection execution.

    Answers:
    - What projection was produced?
    - Under which contract?
    - What semantic state identity did it have?

    The receipt carries the overall fingerprint only.
    Section fingerprints remain in the full fingerprint snapshot
    on the execution result to keep the receipt compact.

    Attributes:
        projection_name: Stable identifier for this projection type
        contract_version: Optional contract version active at execution time
        fingerprint: The overall semantic fingerprint of the projection
    """

    projection_name: str

    contract_version: (
        Optional[str]
    ) = None

    fingerprint: (
        Optional[ResearchWorkspaceConsumerProjectionFingerprint]
    ) = None
