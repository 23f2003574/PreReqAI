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

from .json_research_session_branch_store import (
    JsonResearchSessionBranchStore,
)

from .json_research_session_profile_store import (
    JsonResearchSessionProfileStore,
)

from .json_research_tag_store import (
    JsonResearchTagStore,
)

from .json_research_collection_store import (
    JsonResearchCollectionStore,
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

            "session_branch_store": (

                JsonResearchSessionBranchStore(

                    config.session_branches_path
                )
            ),

            "session_profile_store": (

                JsonResearchSessionProfileStore(

                    config.session_profiles_path
                )
            ),

            "tag_store": (

                JsonResearchTagStore(

                    config.research_tags_path
                )
            ),

            "collection_store": (

                JsonResearchCollectionStore(

                    config
                    .research_collections_path
                )
            ),
        }
