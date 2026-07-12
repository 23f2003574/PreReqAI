from dataclasses import (
    asdict,
    dataclass,
)

from datetime import datetime


@dataclass
class ResearchRecoveryResult:
    """
    Describes the outcome of a
    successful checkpoint recovery.
    """

    session_id: str

    source_checkpoint_id: str

    source_version_id: str

    safety_checkpoint_id: str

    recovery_checkpoint_id: str

    recovered_at: datetime

    def to_dict(self):

        data = asdict(self)

        data["recovered_at"] = (
            self.recovered_at.isoformat()
        )

        return data
