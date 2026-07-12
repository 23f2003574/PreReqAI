from copy import deepcopy

from .interaction_artifact_link import (
    InteractionArtifactLink,
)

from .interaction_artifact_link_store import (
    InteractionArtifactLinkStore,
)


class InMemoryInteractionArtifactLinkStore(
    InteractionArtifactLinkStore
):
    """
    Stores interaction-to-artifact
    correlations in memory.
    """

    def __init__(self):

        self._links: list[
            InteractionArtifactLink
        ] = []

    def save(

        self,

        link:
            InteractionArtifactLink,

    ) -> InteractionArtifactLink:

        exists = any(

            existing.interaction_id
            == link.interaction_id

            and

            existing.artifact_id
            == link.artifact_id

            for existing

            in self._links
        )

        if not exists:

            self._links.append(

                deepcopy(
                    link
                )
            )

        return deepcopy(
            link
        )

    def list_for_interaction(

        self,

        interaction_id: str,

    ) -> list[
        InteractionArtifactLink
    ]:

        return self._matching(

            lambda link: (

                link.interaction_id

                == interaction_id
            )
        )

    def list_for_artifact(

        self,

        artifact_id: str,

    ) -> list[
        InteractionArtifactLink
    ]:

        return self._matching(

            lambda link: (

                link.artifact_id

                == artifact_id
            )
        )

    def list_for_session(

        self,

        session_id: str,

    ) -> list[
        InteractionArtifactLink
    ]:

        return self._matching(

            lambda link: (

                link.session_id

                == session_id
            )
        )

    def _matching(

        self,

        predicate,

    ):

        return [

            deepcopy(
                link
            )

            for link

            in self._links

            if predicate(
                link
            )
        ]
