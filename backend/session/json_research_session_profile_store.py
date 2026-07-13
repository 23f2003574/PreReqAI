from pathlib import Path

from backend.storage import (
    AtomicJsonFile,
)

from .research_session_profile import (
    ResearchSessionProfile,
)

from .research_session_profile_store import (
    ResearchSessionProfileStore,
)


class JsonResearchSessionProfileStore(
    ResearchSessionProfileStore
):
    """
    Persists mutable research session
    profiles to JSON.
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

        profile:
            ResearchSessionProfile,

    ) -> ResearchSessionProfile:

        profiles = (
            self.file.read()
        )

        profiles[
            profile.session_id
        ] = profile.to_dict()

        self.file.write(
            profiles
        )

        return (

            ResearchSessionProfile
            .from_dict(

                profile.to_dict()
            )
        )

    def get(

        self,

        session_id: str,

    ) -> ResearchSessionProfile | None:

        profiles = (
            self.file.read()
        )

        data = profiles.get(
            session_id
        )

        if data is None:

            return None

        return (

            ResearchSessionProfile
            .from_dict(

                data
            )
        )

    def list_all(

        self,

    ) -> list[
        ResearchSessionProfile
    ]:

        profiles = (
            self.file.read()
        )

        restored = [

            ResearchSessionProfile
            .from_dict(

                data
            )

            for data

            in profiles.values()
        ]

        return sorted(

            restored,

            key=lambda item: (
                item.created_at,
                item.session_id,
            ),
        )
