from dataclasses import (
    asdict,
    dataclass,
    field,
)

from datetime import datetime

from typing import Any

from uuid import uuid4

from .research_artifact_type import (
    ResearchArtifactType,
)


@dataclass
class ResearchArtifact:
    """
    Represents a durable output generated
    during a research-learning session.
    """

    session_id: str

    object_id: str

    artifact_type: (
        ResearchArtifactType
    )

    content: Any

    id: str = field(
        default_factory=lambda:
            str(uuid4()),
    )

    action: str | None = None

    title: str | None = None

    content_type: str = "text"

    version: int = 1

    metadata: dict[
        str,
        Any,
    ] = field(
        default_factory=dict,
    )

    created_at: datetime = field(
        default_factory=datetime.utcnow,
    )

    updated_at: datetime = field(
        default_factory=datetime.utcnow,
    )

    def to_dict(self):

        data = asdict(self)

        data["artifact_type"] = (
            self.artifact_type.value
        )

        data["created_at"] = (
            self.created_at.isoformat()
        )

        data["updated_at"] = (
            self.updated_at.isoformat()
        )

        return data

    @classmethod
    def from_dict(

        cls,

        data: dict,

    ):

        payload = dict(data)

        payload["artifact_type"] = (

            ResearchArtifactType(

                payload[
                    "artifact_type"
                ]
            )
        )

        for field_name in (

            "created_at",

            "updated_at",
        ):

            value = payload.get(
                field_name
            )

            if isinstance(
                value,
                str,
            ):

                payload[field_name] = (

                    datetime.fromisoformat(
                        value
                    )
                )

        return cls(
            **payload
        )
