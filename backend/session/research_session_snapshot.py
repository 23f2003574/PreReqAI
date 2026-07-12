from dataclasses import (
    asdict,
    dataclass,
    field,
)

from datetime import datetime

from typing import Any


@dataclass
class ResearchSessionSnapshot:
    """
    Represents a serializable snapshot
    of a research-learning session.
    """

    session_id: str

    paper_id: str | None = None

    paper_title: str | None = None

    active_view: str = "paper"

    selected_object_id: str | None = None

    selected_section_id: str | None = None

    selected_graph_node_id: str | None = None

    breadcrumbs: list[dict] = field(
        default_factory=list,
    )

    timeline: list[dict] = field(
        default_factory=list,
    )

    interaction_history: list[dict] = field(
        default_factory=list,
    )

    recommendations: list[dict] = field(
        default_factory=list,
    )

    metadata: dict[str, Any] = field(
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
