from dataclasses import (
    dataclass,
    field,
)

from datetime import datetime, timezone

from .object_action import (
    ObjectAction,
)


@dataclass
class InteractionEvent:
    """
    Represents one interaction with
    a research object.
    """

    object_id: str

    object_title: str

    action: ObjectAction

    timestamp: datetime = field(
        default_factory=lambda: datetime.now(
            timezone.utc,
        ),
    )


@dataclass
class InteractionHistory:
    """
    Stores the learner's interaction
    history across research objects.
    """

    events: list[
        InteractionEvent
    ] = field(
        default_factory=list,
    )

    def record(
        self,
        object_id: str,
        object_title: str,
        action: ObjectAction,
    ):

        self.events.append(
            InteractionEvent(
                object_id=object_id,
                object_title=object_title,
                action=action,
            )
        )

    def recent(
        self,
        limit: int = 20,
    ):

        return self.events[-limit:]

    def has_completed(
        self,
        object_id: str,
        action: ObjectAction,
    ) -> bool:

        return any(
            event.object_id == object_id
            and event.action == action

            for event in self.events
        )
