from copy import deepcopy

from .research_checkpoint import (
    ResearchCheckpoint,
)

from .research_checkpoint_store import (
    ResearchCheckpointStore,
)


class InMemoryResearchCheckpointStore(
    ResearchCheckpointStore
):
    """
    Stores research checkpoint history
    in memory for development and tests.
    """

    def __init__(self):

        self._checkpoints: dict[

            str,

            ResearchCheckpoint,

        ] = {}

    def save(

        self,

        checkpoint:
            ResearchCheckpoint,

    ) -> ResearchCheckpoint:

        stored = deepcopy(
            checkpoint
        )

        self._checkpoints[
            checkpoint.id
        ] = stored

        return deepcopy(
            stored
        )

    def get(

        self,

        checkpoint_id: str,

    ) -> ResearchCheckpoint | None:

        checkpoint = (

            self._checkpoints.get(

                checkpoint_id
            )
        )

        if checkpoint is None:

            return None

        return deepcopy(
            checkpoint
        )

    def list_for_session(

        self,

        session_id: str,

    ) -> list[
        ResearchCheckpoint
    ]:

        checkpoints = [

            checkpoint

            for checkpoint

            in self._checkpoints.values()

            if (

                checkpoint.session_id

                == session_id
            )
        ]

        return [

            deepcopy(
                checkpoint
            )

            for checkpoint

            in sorted(

                checkpoints,

                key=lambda item:
                    item.created_at,
            )
        ]

    def latest_for_session(

        self,

        session_id: str,

    ) -> ResearchCheckpoint | None:

        checkpoints = (

            self.list_for_session(

                session_id
            )
        )

        if not checkpoints:

            return None

        return checkpoints[-1]

    def delete(

        self,

        checkpoint_id: str,

    ) -> bool:

        if (

            checkpoint_id

            not in self._checkpoints
        ):

            return False

        del self._checkpoints[
            checkpoint_id
        ]

        return True

    def list_all(

        self,

    ) -> list[
        ResearchCheckpoint
    ]:

        return [

            deepcopy(
                checkpoint
            )

            for checkpoint

            in sorted(

                self._checkpoints.values(),

                key=lambda item:
                    item.created_at,
            )
        ]

    def export_state(self):

        return deepcopy(
            self._checkpoints
        )

    def restore_state(

        self,

        state,

    ) -> None:

        self._checkpoints = deepcopy(
            state
        )
