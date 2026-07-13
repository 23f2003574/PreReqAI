from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from typing import (
    Any,
)

from uuid import (
    uuid4,
)

from .research_workspace_change_operation import (
    ResearchWorkspaceChangeOperation,
)


@dataclass
class ResearchWorkspaceChangeEvent:
    """
    Represents one ordered workspace
    state change for reactive consumers.
    """

    event_id: str

    sequence: int

    operation: (
        ResearchWorkspaceChangeOperation
    )

    entity_type: str

    entity_id: (
        str | None
    )

    occurred_at: datetime

    related_entity_ids: list[
        str
    ] = field(
        default_factory=list,
    )

    metadata: dict[
        str,
        Any,
    ] = field(
        default_factory=dict,
    )

    @classmethod
    def create(

        cls,

        sequence,

        operation,

        entity_type,

        entity_id=None,

        related_entity_ids=None,

        metadata=None,

        event_id=None,

        occurred_at=None,

    ):

        return cls(

            event_id=(

                event_id

                or str(
                    uuid4()
                )
            ),

            sequence=(
                sequence
            ),

            operation=(
                operation
            ),

            entity_type=(
                entity_type
            ),

            entity_id=(
                entity_id
            ),

            occurred_at=(

                occurred_at

                or datetime.now(
                    timezone.utc
                )
            ),

            related_entity_ids=(

                list(
                    related_entity_ids
                    or []
                )
            ),

            metadata=(

                dict(
                    metadata
                    or {}
                )
            ),
        )

    def to_dict(self):

        return {

            "event_id":
                self.event_id,

            "sequence":
                self.sequence,

            "operation":
                self.operation.value,

            "entity_type":
                self.entity_type,

            "entity_id":
                self.entity_id,

            "occurred_at":
                self.occurred_at
                .isoformat(),

            "related_entity_ids":
                list(
                    self.related_entity_ids
                ),

            "metadata":
                dict(
                    self.metadata
                ),
        }

    @classmethod
    def from_dict(

        cls,

        data,

    ):

        return cls(

            event_id=(
                data[
                    "event_id"
                ]
            ),

            sequence=(
                data[
                    "sequence"
                ]
            ),

            operation=(

                ResearchWorkspaceChangeOperation(

                    data[
                        "operation"
                    ]
                )
            ),

            entity_type=(
                data[
                    "entity_type"
                ]
            ),

            entity_id=(
                data.get(
                    "entity_id"
                )
            ),

            occurred_at=(

                datetime.fromisoformat(

                    data[
                        "occurred_at"
                    ]
                )
            ),

            related_entity_ids=(

                list(

                    data.get(

                        "related_entity_ids",

                        [],
                    )
                )
            ),

            metadata=(

                dict(

                    data.get(

                        "metadata",

                        {},
                    )
                )
            ),
        )
