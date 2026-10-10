from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
)

from typing import (
    Any,
)

from .research_activity_actor_type import (
    ResearchActivityActorType,
)

from .research_activity_type import (
    ResearchActivityType,
)


@dataclass
class ResearchActivityEvent:
    """
    Represents one immutable domain-level
    research workspace activity event.
    """

    id: str

    activity_type: (
        ResearchActivityType
    )

    occurred_at: datetime

    session_id: (
        str | None
    ) = None

    related_session_id: (
        str | None
    ) = None

    actor_type: (
        ResearchActivityActorType
    ) = (
        ResearchActivityActorType.SYSTEM
    )

    actor_id: (
        str | None
    ) = None

    metadata: dict[
        str,
        Any,
    ] = field(
        default_factory=dict,
    )

    def to_dict(self):

        return {

            "id":
                self.id,

            "activity_type":
                self.activity_type.value,

            "occurred_at":
                self.occurred_at
                .isoformat(),

            "session_id":
                self.session_id,

            "related_session_id":
                self.related_session_id,

            "actor_type":
                self.actor_type.value,

            "actor_id":
                self.actor_id,

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

            id=data["id"],

            activity_type=(

                ResearchActivityType(

                    data[
                        "activity_type"
                    ]
                )
            ),

            occurred_at=(

                datetime
                .fromisoformat(

                    data[
                        "occurred_at"
                    ]
                )
            ),

            session_id=(

                data.get(
                    "session_id"
                )
            ),

            related_session_id=(

                data.get(
                    "related_session_id"
                )
            ),

            actor_type=(

                ResearchActivityActorType(

                    data.get(

                        "actor_type",

                        "system",
                    )
                )
            ),

            actor_id=(

                data.get(
                    "actor_id"
                )
            ),

            metadata=dict(

                data.get(

                    "metadata",

                    {},
                )
            ),
        )
