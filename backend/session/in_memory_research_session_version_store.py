from copy import deepcopy

from .research_session_version import (
    ResearchSessionVersion,
)

from .research_session_version_store import (
    ResearchSessionVersionStore,
)


class InMemoryResearchSessionVersionStore(
    ResearchSessionVersionStore
):
    """
    Stores immutable historical session
    versions in memory.
    """

    def __init__(self):

        self._versions: dict[

            str,

            ResearchSessionVersion,

        ] = {}

    def save(

        self,

        version:
            ResearchSessionVersion,

    ) -> ResearchSessionVersion:

        if version.id in self._versions:

            raise ValueError(

                "Research session version "
                "already exists: "
                f"{version.id}"
            )

        stored = deepcopy(
            version
        )

        self._versions[
            version.id
        ] = stored

        return deepcopy(
            stored
        )

    def get(

        self,

        version_id: str,

    ) -> ResearchSessionVersion | None:

        version = (

            self._versions.get(
                version_id
            )
        )

        if version is None:

            return None

        return deepcopy(
            version
        )

    def list_for_session(

        self,

        session_id: str,

    ) -> list[
        ResearchSessionVersion
    ]:

        versions = [

            version

            for version

            in self._versions.values()

            if (

                version.session_id

                == session_id
            )
        ]

        return [

            deepcopy(
                version
            )

            for version

            in sorted(

                versions,

                key=lambda item:
                    item.created_at,
            )
        ]

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

        if version_id not in self._versions:

            return False

        del self._versions[
            version_id
        ]

        return True

    def list_all(

        self,

    ) -> list[
        ResearchSessionVersion
    ]:

        return [

            deepcopy(
                version
            )

            for version

            in sorted(

                self._versions.values(),

                key=lambda item:
                    item.created_at,
            )
        ]

    def export_state(self):

        return deepcopy(
            self._versions
        )

    def restore_state(

        self,

        state,

    ) -> None:

        self._versions = deepcopy(
            state
        )
