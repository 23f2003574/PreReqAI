from dataclasses import (
    dataclass,
    field,
)

from datetime import datetime, timezone

from .navigation_target import (
    NavigationTarget,
)


def _utcnow() -> datetime:

    return datetime.now(timezone.utc)


@dataclass
class NavigationEvent:

    target: NavigationTarget

    title: str

    timestamp: datetime = field(
        default_factory=_utcnow,
    )


@dataclass
class NavigationHistory:
    """
    Stores the learner's navigation
    journey through a research paper.
    """

    events: list[NavigationEvent] = field(
        default_factory=list,
    )

    def record(

        self,

        target: NavigationTarget,

        title: str,

    ):

        self.events.append(

            NavigationEvent(

                target=target,

                title=title,
            )
        )

    def recent(

        self,

        limit: int = 10,

    ):

        return self.events[-limit:]
