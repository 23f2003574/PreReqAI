from dataclasses import (
    asdict,
    dataclass,
    field,
)

from datetime import datetime


@dataclass
class ResearchCheckpointAnnotation:
    """
    Stores mutable human-authored
    metadata for a research checkpoint.
    """

    checkpoint_id: str

    session_id: str

    label: str | None = None

    note: str | None = None

    pinned: bool = False

    created_at: datetime = field(
        default_factory=datetime.utcnow,
    )

    updated_at: datetime = field(
        default_factory=datetime.utcnow,
    )

    def to_dict(self):

        data = asdict(self)

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
