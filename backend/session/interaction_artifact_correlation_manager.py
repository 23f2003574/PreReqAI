from .interaction_artifact_link import (
    InteractionArtifactLink,
)

from .interaction_artifact_link_store import (
    InteractionArtifactLinkStore,
)

from .research_artifact_store import (
    ResearchArtifactStore,
)


class InteractionArtifactCorrelationManager:
    """
    Coordinates exact relationships
    between educational interactions
    and durable research artifacts.
    """

    def __init__(

        self,

        link_store:
            InteractionArtifactLinkStore,

        artifact_store:
            ResearchArtifactStore,

    ):

        self.link_store = link_store

        self.artifact_store = (
            artifact_store
        )

    def link(

        self,

        interaction_id: str,

        artifact,

    ):

        link = InteractionArtifactLink(

            interaction_id=str(
                interaction_id
            ),

            artifact_id=(
                artifact.id
            ),

            session_id=(
                artifact.session_id
            ),

            object_id=(
                artifact.object_id
            ),

            action=(

                artifact.action

                or ""
            ),
        )

        return self.link_store.save(
            link
        )

    def links_for_interaction(

        self,

        interaction_id: str,

    ):

        return (

            self.link_store
            .list_for_interaction(

                interaction_id
            )
        )

    def artifacts_for_interaction(

        self,

        interaction_id: str,

    ):

        links = (

            self.links_for_interaction(

                interaction_id
            )
        )

        artifacts = []

        for link in links:

            artifact = (

                self.artifact_store.get(

                    link.artifact_id
                )
            )

            if artifact is not None:

                artifacts.append(
                    artifact
                )

        return artifacts

    def primary_artifact_for_interaction(

        self,

        interaction_id: str,

    ):

        artifacts = (

            self.artifacts_for_interaction(

                interaction_id
            )
        )

        if not artifacts:

            return None

        return artifacts[0]

    def interactions_for_artifact(

        self,

        artifact_id: str,

    ):

        return (

            self.link_store
            .list_for_artifact(

                artifact_id
            )
        )
