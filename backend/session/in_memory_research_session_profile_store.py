from copy import deepcopy

from .research_session_profile import (
    ResearchSessionProfile,
)

from .research_session_profile_store import (
    ResearchSessionProfileStore,
)


class InMemoryResearchSessionProfileStore(
    ResearchSessionProfileStore
):
    """
    Stores mutable research session
    profiles in memory.
    """

    def __init__(self):

        self._profiles: dict[

            str,

            ResearchSessionProfile,

        ] = {}

    def save(

        self,

        profile:
            ResearchSessionProfile,

    ) -> ResearchSessionProfile:

        stored = deepcopy(
            profile
        )

        self._profiles[
            profile.session_id
        ] = stored

        return deepcopy(
            stored
        )

    def get(

        self,

        session_id: str,

    ) -> ResearchSessionProfile | None:

        profile = (

            self._profiles.get(
                session_id
            )
        )

        if profile is None:

            return None

        return deepcopy(
            profile
        )

    def list_all(

        self,

    ) -> list[
        ResearchSessionProfile
    ]:

        return [

            deepcopy(
                profile
            )

            for profile

            in sorted(

                self._profiles.values(),

                key=lambda item: (
                    item.created_at,
                    item.session_id,
                ),
            )
        ]

    def export_state(self):

        return deepcopy(
            self._profiles
        )

    def restore_state(

        self,

        state,

    ) -> None:

        self._profiles = deepcopy(
            state
        )
