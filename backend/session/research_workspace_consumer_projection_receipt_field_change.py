from dataclasses import (
    dataclass,
)

from typing import (
    Optional,
)

from .research_workspace_consumer_projection_receipt_change_kind import (
    ResearchWorkspaceConsumerProjectionReceiptChangeKind,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionReceiptFieldChange:
    """
    One changed comparison dimension between two consumer
    projection execution receipts.

    Represents a single, compact difference - not an embedded
    copy of either receipt. Values are compact string
    representations suitable for logging and debugging.

    Attributes:
        field: Name of the compared dimension (e.g. "status")
        kind: Directional classification of the difference
        previous: Compact representation of the previous value
        current: Compact representation of the current value
    """

    field: str

    kind: (
        ResearchWorkspaceConsumerProjectionReceiptChangeKind
    )

    previous: (
        Optional[str]
    ) = None

    current: (
        Optional[str]
    ) = None
