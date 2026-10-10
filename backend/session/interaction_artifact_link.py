from dataclasses import (
    asdict,
    dataclass,
    field,
)

from datetime import datetime

from typing import Any


@dataclass
class InteractionArtifactLink:
    """
    Links one educational interaction
    to the exact durable artifact
    produced by that interaction.
    """

    interaction_id: str

    artifact_id: str

    session_id: str

    object_id: str

    action: str

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
