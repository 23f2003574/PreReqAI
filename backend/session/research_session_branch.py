from dataclasses import (
    asdict,
    dataclass,
    field,
)

from datetime import datetime

from typing import Any

from uuid import uuid4


@dataclass
class ResearchSessionBranch:
    """
    Represents the lineage relationship
    between a source research checkpoint
    and a newly created research session.
    """

    source_session_id: str

    source_checkpoint_id: str

    source_version_id: str

    branch_session_id: str

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

        data["created_at"] = (
            self.created_at.isoformat()
        )

        return data

    @classmethod
    def from_dict(

        cls,

        data: dict,

    ):

        payload = dict(data)

        created_at = payload.get(
            "created_at"
        )

        if isinstance(
            created_at,
            str,
        ):

            payload["created_at"] = (

                datetime.fromisoformat(
                    created_at
                )
            )

        return cls(
            **payload
        )
