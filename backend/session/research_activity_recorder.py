from datetime import (
    datetime,
    timezone,
)

from uuid import (
    uuid4,
)

from .research_activity_actor_type import (
    ResearchActivityActorType,
)

from .research_activity_event import (
    ResearchActivityEvent,
)


class ResearchActivityRecorder:
    """
    Creates and appends immutable
    research activity events.
    """

    def __init__(

        self,

        activity_store,

        clock=None,

        id_factory=None,

    ):

        self.activity_store = (
            activity_store
        )

        self.clock = (
            clock
        )

        self.id_factory = (
            id_factory
        )

    def _now(self):

        if self.clock is not None:

            return self.clock()

        return datetime.now(
            timezone.utc
        )

    def _new_id(self):

        if self.id_factory is not None:

            return self.id_factory()

        return str(
            uuid4()
        )

    def record(

        self,

        activity_type,

        session_id=None,

        related_session_id=None,

        actor_type=(
            ResearchActivityActorType.SYSTEM
        ),

        actor_id=None,

        metadata=None,

    ):

        event = (

            ResearchActivityEvent(

                id=(
                    self._new_id()
                ),

                activity_type=(
                    activity_type
                ),

                occurred_at=(
                    self._now()
                ),

                session_id=(
                    session_id
                ),

                related_session_id=(
                    related_session_id
                ),

                actor_type=(
                    actor_type
                ),

                actor_id=(
                    actor_id
                ),

                metadata=dict(

                    metadata or {}
                ),
            )
        )

        self.activity_store.append(

            event
        )

        return event
