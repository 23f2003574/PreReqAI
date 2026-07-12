from dataclasses import (
    asdict,
    dataclass,
    field,
)

from datetime import datetime

from typing import Any

from uuid import uuid4

from .research_checkpoint_reason import (
    ResearchCheckpointReason,
)


@dataclass
class ResearchCheckpoint:
    """
    Represents a recorded persistence
    checkpoint for a research session.
    """

    session_id: str

    reason: (
        ResearchCheckpointReason
    )

    snapshot_updated_at: datetime

    id: str = field(
        default_factory=lambda:
            str(uuid4()),
    )

    metadata: dict[
        str,
        Any,
    ] = field(
        default_factory=dict,
    )

    created_at: datetime = field(
        default_factory=datetime.utcnow,
    )

    def to_dict(self):

        data = asdict(self)

        data["reason"] = (
            self.reason.value
        )

        data["snapshot_updated_at"] = (
            self.snapshot_updated_at
            .isoformat()
        )

        data["created_at"] = (
            self.created_at.isoformat()
        )

        return data
