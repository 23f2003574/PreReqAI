from .json_interaction_artifact_link_store import (
    JsonInteractionArtifactLinkStore,
)

from .json_research_artifact_store import (
    JsonResearchArtifactStore,
)

from .json_research_checkpoint_annotation_store import (
    JsonResearchCheckpointAnnotationStore,
)

from .json_research_checkpoint_store import (
    JsonResearchCheckpointStore,
)

from .json_research_session_store import (
    JsonResearchSessionStore,
)

from .json_research_session_version_store import (
    JsonResearchSessionVersionStore,
)

from .research_persistence_config import (
    ResearchPersistenceConfig,
)


class ResearchPersistenceFactory:
    """
    Creates filesystem-backed research
    persistence stores.
    """

    @staticmethod
    def create(

        config:
            ResearchPersistenceConfig,

    ):

        return {

            "session_store": (

                JsonResearchSessionStore(

                    config.sessions_path
                )
            ),

            "artifact_store": (

                JsonResearchArtifactStore(

                    config.artifacts_path
                )
            ),

            "interaction_link_store": (

                JsonInteractionArtifactLinkStore(

                    config
                    .interaction_links_path
                )
            ),

            "checkpoint_store": (

                JsonResearchCheckpointStore(

                    config.checkpoints_path
                )
            ),

            "session_version_store": (

                JsonResearchSessionVersionStore(

                    config
                    .session_versions_path
                )
            ),

            "checkpoint_annotation_store": (

                JsonResearchCheckpointAnnotationStore(

                    config
                    .checkpoint_annotations_path
                )
            ),
        }
