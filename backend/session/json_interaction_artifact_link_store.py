from pathlib import Path

from backend.storage import (
    AtomicJsonFile,
)

from .interaction_artifact_link import (
    InteractionArtifactLink,
)

from .interaction_artifact_link_store import (
    InteractionArtifactLinkStore,
)


class JsonInteractionArtifactLinkStore(
    InteractionArtifactLinkStore
):
    """
    Persists interaction-to-artifact
    correlations to a JSON file.
    """

    def __init__(

        self,

        path: str | Path,

    ):

        self.file = AtomicJsonFile(

            path,

            default_factory=list,
        )

    def save(

        self,

        link:
            InteractionArtifactLink,

    ) -> InteractionArtifactLink:

        links = self.file.read()

        exists = any(

            item.get(
                "interaction_id"
            )

            == link.interaction_id

            and

            item.get(
                "artifact_id"
            )

            == link.artifact_id

            for item in links
        )

        if not exists:

            links.append(

                link.to_dict()
            )

            self.file.write(
                links
            )

        return link

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

        links = self.file.read()

        result = []

        for data in links:

            link = (

                InteractionArtifactLink
                .from_dict(

                    data
                )
            )

            if predicate(
                link
            ):

                result.append(
                    link
                )

        return result
