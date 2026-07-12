from .research_artifact import (
    ResearchArtifact,
)

from .research_artifact_type import (
    ResearchArtifactType,
)

from .research_artifact_store import (
    ResearchArtifactStore,
)


class ResearchArtifactManager:
    """
    Coordinates creation and persistence
    of generated research artifacts.
    """

    def __init__(

        self,

        store:
            ResearchArtifactStore,

    ):

        self.store = store

    def create(

        self,

        session_id: str,

        object_id: str,

        artifact_type:
            ResearchArtifactType,

        content,

        action: str | None = None,

        title: str | None = None,

        content_type: str = "text",

        metadata: dict | None = None,

    ):

        version = (

            self._next_version(

                session_id=session_id,

                object_id=object_id,

                artifact_type=(
                    artifact_type
                ),

                action=action,
            )
        )

        artifact = ResearchArtifact(

            session_id=session_id,

            object_id=object_id,

            artifact_type=(
                artifact_type
            ),

            content=content,

            action=action,

            title=title,

            content_type=content_type,

            version=version,

            metadata=(

                metadata

                if metadata is not None

                else {}
            ),
        )

        return self.store.save(
            artifact
        )

    def get(

        self,

        artifact_id: str,

    ):

        return self.store.get(
            artifact_id
        )

    def for_session(

        self,

        session_id: str,

    ):

        return (

            self.store
            .list_for_session(

                session_id
            )
        )

    def for_object(

        self,

        session_id: str,

        object_id: str,

    ):

        return (

            self.store
            .list_for_object(

                session_id,

                object_id,
            )
        )

    def delete(

        self,

        artifact_id: str,

    ):

        return self.store.delete(
            artifact_id
        )

    def _next_version(

        self,

        session_id: str,

        object_id: str,

        artifact_type:
            ResearchArtifactType,

        action: str | None,

    ):

        matching = [

            artifact

            for artifact

            in self.for_object(

                session_id,

                object_id,
            )

            if (

                artifact.artifact_type

                == artifact_type

                and

                artifact.action

                == action
            )
        ]

        if not matching:

            return 1

        return (

            max(

                artifact.version

                for artifact

                in matching
            )

            + 1
        )
