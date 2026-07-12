from pathlib import Path

from backend.storage import (
    AtomicJsonFile,
)

from .research_session_version import (
    ResearchSessionVersion,
)

from .research_session_version_store import (
    ResearchSessionVersionStore,
)


class JsonResearchSessionVersionStore(
    ResearchSessionVersionStore
):
    """
    Persists immutable historical
    research session versions.
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

        version:
            ResearchSessionVersion,

    ) -> ResearchSessionVersion:

        versions = self.file.read()

        if version.id in versions:

            raise ValueError(

                "Research session version "
                "already exists: "
                f"{version.id}"
            )

        versions[
            version.id
        ] = version.to_dict()

        self.file.write(
            versions
        )

        return (

            ResearchSessionVersion
            .from_dict(

                version.to_dict()
            )
        )

    def get(

        self,

        version_id: str,

    ) -> ResearchSessionVersion | None:

        versions = self.file.read()

        data = versions.get(
            version_id
        )

        if data is None:

            return None

        return (

            ResearchSessionVersion
            .from_dict(

                data
            )
        )

    def list_for_session(

        self,

        session_id: str,

    ) -> list[
        ResearchSessionVersion
    ]:

        versions = self.file.read()

        matching = []

        for data in versions.values():

            version = (

                ResearchSessionVersion
                .from_dict(

                    data
                )
            )

            if (

                version.session_id

                == session_id
            ):

                matching.append(
                    version
                )

        return sorted(

            matching,

            key=lambda item:
                item.created_at,
        )

    def latest_for_session(

        self,

        session_id: str,

    ) -> ResearchSessionVersion | None:

        versions = (

            self.list_for_session(

                session_id
            )
        )

        if not versions:

            return None

        return versions[-1]

    def delete(

        self,

        version_id: str,

    ) -> bool:

        versions = self.file.read()

        if version_id not in versions:

            return False

        del versions[
            version_id
        ]

        self.file.write(
            versions
        )

        return True
