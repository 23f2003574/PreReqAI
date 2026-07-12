from copy import deepcopy

from datetime import datetime

from pathlib import Path

from backend.storage import (
    AtomicJsonFile,
)

from .research_artifact import (
    ResearchArtifact,
)

from .research_artifact_store import (
    ResearchArtifactStore,
)


class JsonResearchArtifactStore(
    ResearchArtifactStore
):
    """
    Persists durable research artifacts
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

        artifact:
            ResearchArtifact,

    ) -> ResearchArtifact:

        artifact.updated_at = (
            datetime.utcnow()
        )

        artifacts = self.file.read()

        artifacts[
            artifact.id
        ] = artifact.to_dict()

        self.file.write(
            artifacts
        )

        return deepcopy(
            artifact
        )

    def get(

        self,

        artifact_id: str,

    ) -> ResearchArtifact | None:

        artifacts = self.file.read()

        data = artifacts.get(
            artifact_id
        )

        if data is None:

            return None

        return (

            ResearchArtifact
            .from_dict(

                data
            )
        )

    def delete(

        self,

        artifact_id: str,

    ) -> bool:

        artifacts = self.file.read()

        if artifact_id not in artifacts:

            return False

        del artifacts[
            artifact_id
        ]

        self.file.write(
            artifacts
        )

        return True

    def list_for_session(

        self,

        session_id: str,

    ) -> list[
        ResearchArtifact
    ]:

        return self._matching(

            lambda artifact: (

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

        return self._matching(

            lambda artifact: (

                artifact.session_id

                == session_id

                and

                artifact.object_id

                == object_id
            )
        )

    def _matching(

        self,

        predicate,

    ):

        artifacts = self.file.read()

        matching = []

        for data in artifacts.values():

            artifact = (

                ResearchArtifact
                .from_dict(

                    data
                )
            )

            if predicate(
                artifact
            ):

                matching.append(
                    artifact
                )

        return sorted(

            matching,

            key=lambda item:
                item.created_at,
        )
