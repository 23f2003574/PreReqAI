from dataclasses import (
    asdict,
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from typing import Any

from .research_session_status import (
    ResearchSessionStatus,
)


def utc_now():

    return datetime.now(
        timezone.utc
    )


@dataclass
class ResearchSessionProfile:
    """
    Stores mutable human-facing metadata
    for a research session.
    """

    session_id: str

    display_name: str | None = None

    description: str | None = None

    status: (
        ResearchSessionStatus
    ) = (
        ResearchSessionStatus.ACTIVE
    )

    archived: bool = False

    metadata: dict[
        str,
        Any,
    ] = field(
        default_factory=dict,
    )

    created_at: datetime = field(
        default_factory=utc_now,
    )

    updated_at: datetime = field(
        default_factory=utc_now,
    )

    def __post_init__(self):

        if not isinstance(

            self.status,

            ResearchSessionStatus,
        ):

            self.status = (

                ResearchSessionStatus(

                    self.status
                )
            )

        if self.display_name is not None:

            self.display_name = (

                self.display_name.strip()

                or None
            )

        if self.description is not None:

            self.description = (

                self.description.strip()

                or None
            )

    def to_dict(self):

        data = asdict(
            self
        )

        data["status"] = (
            self.status.value
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

        payload = dict(
            data
        )

        payload["status"] = (

            ResearchSessionStatus(

                payload.get(

                    "status",

                    ResearchSessionStatus
                    .ACTIVE
                    .value,
                )
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

                payload[
                    field_name
                ] = (

                    datetime
                    .fromisoformat(

                        value
                    )
                )

        return cls(
            **payload
        )
