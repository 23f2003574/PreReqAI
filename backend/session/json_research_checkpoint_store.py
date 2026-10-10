from pathlib import Path

from backend.storage import (
    AtomicJsonFile,
)

from .research_checkpoint import (
    ResearchCheckpoint,
)

from .research_checkpoint_store import (
    ResearchCheckpointStore,
)


class JsonResearchCheckpointStore(
    ResearchCheckpointStore
):
    """
    Persists research checkpoint history
    to a JSON file.
    """

    def __init__(

        self,

        path: str | Path,

    ):

        self.file = AtomicJsonFile(

            path,

            default_factory=dict,
        )

    def save(

        self,

        checkpoint:
            ResearchCheckpoint,

    ) -> ResearchCheckpoint:

        checkpoints = (
            self.file.read()
        )

        checkpoints[
            checkpoint.id
        ] = checkpoint.to_dict()

        self.file.write(
            checkpoints
        )

        return (

            ResearchCheckpoint
            .from_dict(

                checkpoint.to_dict()
            )
        )

    def get(

        self,

        checkpoint_id: str,

    ) -> ResearchCheckpoint | None:

        checkpoints = (
            self.file.read()
        )

        data = checkpoints.get(
            checkpoint_id
        )

        if data is None:

            return None

        return (

            ResearchCheckpoint
            .from_dict(

                data
            )
        )

    def list_for_session(

        self,

        session_id: str,

    ) -> list[
        ResearchCheckpoint
    ]:

        checkpoints = (
            self.file.read()
        )

        matching = []

        for data in checkpoints.values():

            checkpoint = (

                ResearchCheckpoint
                .from_dict(

                    data
                )
            )

            if (

                checkpoint.session_id

                == session_id
            ):

                matching.append(
                    checkpoint
                )

        return sorted(

            matching,

            key=lambda item:
                item.created_at,
        )

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

        checkpoints = (
            self.file.read()
        )

        if (

            checkpoint_id

            not in checkpoints
        ):

            return False

        del checkpoints[
            checkpoint_id
        ]

        self.file.write(
            checkpoints
        )

        return True

    def export_state(self):

        return self.file.read()

    def restore_state(

        self,

        state,

    ) -> None:

        self.file.write(
            state
        )

    def list_all(

        self,

    ) -> list[
        ResearchCheckpoint
    ]:

        checkpoints = (
            self.file.read()
        )

        restored = [

            ResearchCheckpoint
            .from_dict(

                data
            )

            for data

            in checkpoints.values()
        ]

        return sorted(

            restored,

            key=lambda item:
                item.created_at,
        )
