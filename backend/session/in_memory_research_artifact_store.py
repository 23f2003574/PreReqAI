from copy import deepcopy

from datetime import datetime

from .research_artifact import (
    ResearchArtifact,
)

from .research_artifact_store import (
    ResearchArtifactStore,
)


class InMemoryResearchArtifactStore(
    ResearchArtifactStore
):
    """
    Stores generated research artifacts
    in memory for development and testing.
    """

    def __init__(self):

        self._artifacts: dict[

            str,

            ResearchArtifact,

        ] = {}

    def save(

        self,

        artifact:
            ResearchArtifact,

    ) -> ResearchArtifact:

        artifact.updated_at = (
            datetime.utcnow()
        )

        stored = deepcopy(
            artifact
        )

        self._artifacts[
            artifact.id
        ] = stored

        return deepcopy(
            stored
        )

    def get(

        self,

        artifact_id: str,

    ) -> ResearchArtifact | None:

        artifact = (
            self._artifacts.get(
                artifact_id
            )
        )

        if artifact is None:

            return None

        return deepcopy(
            artifact
        )

    def delete(

        self,

        artifact_id: str,

    ) -> bool:

        if (

            artifact_id

            not in self._artifacts
        ):

            return False

        del self._artifacts[
            artifact_id
        ]

        return True

    def list_for_session(

        self,

        session_id: str,

    ) -> list[
        ResearchArtifact
    ]:

        return self._sorted(

            artifact

            for artifact

            in self._artifacts.values()

            if (

                artifact.session_id

                == session_id
            )
        )

    def list_for_object(

        self,

        session_id: str,

        object_id: str,

    ) -> list[
        ResearchArtifact
    ]:

        return self._sorted(

            artifact

            for artifact

            in self._artifacts.values()

            if (

                artifact.session_id

                == session_id

                and

                artifact.object_id

                == object_id
            )
        )

    @staticmethod
    def _sorted(

        artifacts,

    ):

        return [

            deepcopy(
                artifact
            )

            for artifact

            in sorted(

                artifacts,

                key=lambda item:
                    item.created_at,
            )
        ]
