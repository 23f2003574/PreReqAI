from frontend.src.workspace import (
    create_visual_research_workspace,
)

from backend.session import (
    InMemoryInteractionArtifactLinkStore,
    InMemoryResearchArtifactStore,
    InMemoryResearchSessionStore,
    InteractionArtifactCorrelationManager,
    ResearchArtifactManager,
    ResearchArtifactTypeMapper,
    ResearchRuntimeRegistry,
    ResearchRuntimeResolver,
    ResearchSessionManager,
    ResearchSessionRestorer,
    ResearchSessionSerializer,
)


class PreReqAIApplication:
    """
    Application-level entry point
    for the visual PreReqAI experience.
    """

    def __init__(self):

        self.artifact_store = (
            InMemoryResearchArtifactStore()
        )

        self.artifact_manager = (
            ResearchArtifactManager(

                self.artifact_store
            )
        )

        self.interaction_artifact_link_store = (

            InMemoryInteractionArtifactLinkStore()
        )

        self.interaction_artifact_correlations = (

            InteractionArtifactCorrelationManager(

                link_store=(

                    self
                    .interaction_artifact_link_store
                ),

                artifact_store=(
                    self.artifact_store
                ),
            )
        )

        self.workspace = (

            create_visual_research_workspace(

                correlation_provider=(

                    self
                    .interaction_artifact_correlations
                )
            )
        )

        self.session_store = (
            InMemoryResearchSessionStore()
        )

        self.runtime_registry = (
            ResearchRuntimeRegistry()
        )

        self.runtime_resolver = (
            ResearchRuntimeResolver(

                self.runtime_registry
            )
        )

        self.session_restorer = (
            ResearchSessionRestorer(

                self.runtime_resolver
            )
        )

        self.session_serializer = (
            ResearchSessionSerializer(

                artifact_manager=(
                    self.artifact_manager
                )
            )
        )

        self.session_manager = (
            ResearchSessionManager(

                self.session_store,

                serializer=(
                    self.session_serializer
                ),

                restorer=(
                    self.session_restorer
                ),
            )
        )

    def save_research_session(

        self,

        session_id: str,

        paper_id: str | None = None,

        paper_title: str | None = None,

    ):

        return (

            self.session_manager
            .save_workspace(

                session_id=session_id,

                workspace=self.workspace,

                paper_id=paper_id,

                paper_title=paper_title,
            )
        )

    def get_research_session(

        self,

        session_id: str,

    ):

        return (

            self.session_manager
            .load_session(

                session_id
            )
        )

    def research_sessions(self):

        return (

            self.session_manager
            .list_sessions()
        )

    def restore_research_session(

        self,

        session_id: str,

    ):

        return (

            self.session_manager
            .restore_workspace(

                session_id,

                self.workspace,
            )
        )

    def register_research_objects(

        self,

        research_objects,

    ):

        (

            self.runtime_registry
            .register_objects(

                research_objects
            )
        )

    def register_research_sections(

        self,

        sections,

    ):

        (

            self.runtime_registry
            .register_sections(

                sections
            )
        )

    def register_graph_nodes(

        self,

        graph_nodes,

    ):

        (

            self.runtime_registry
            .register_graph_nodes(

                graph_nodes
            )
        )

    def save_learning_artifact(

        self,

        session_id: str,

        object_id: str,

        action,

        content,

        title: str | None = None,

        content_type: str = "text",

        metadata: dict | None = None,

    ):

        artifact_type = (

            ResearchArtifactTypeMapper
            .from_action(

                action
            )
        )

        return (

            self.artifact_manager
            .create(

                session_id=session_id,

                object_id=object_id,

                artifact_type=(
                    artifact_type
                ),

                content=content,

                action=(

                    action.value

                    if hasattr(
                        action,
                        "value",
                    )

                    else str(action)
                ),

                title=title,

                content_type=(
                    content_type
                ),

                metadata=metadata,
            )
        )

    def research_artifacts(

        self,

        session_id: str,

    ):

        return (

            self.artifact_manager
            .for_session(

                session_id
            )
        )

    def research_artifacts_for_object(

        self,

        session_id: str,

        object_id: str,

    ):

        return (

            self.artifact_manager
            .for_object(

                session_id,

                object_id,
            )
        )

    def link_interaction_artifact(

        self,

        interaction_id: str,

        artifact,

    ):

        return (

            self.interaction_artifact_correlations
            .link(

                interaction_id,

                artifact,
            )
        )

    def artifacts_for_interaction(

        self,

        interaction_id: str,

    ):

        return (

            self.interaction_artifact_correlations
            .artifacts_for_interaction(

                interaction_id
            )
        )

    def primary_artifact_for_interaction(

        self,

        interaction_id: str,

    ):

        return (

            self.interaction_artifact_correlations
            .primary_artifact_for_interaction(

                interaction_id
            )
        )

    def save_interaction_artifact(

        self,

        interaction_id: str,

        session_id: str,

        object_id: str,

        action,

        content,

        title: str | None = None,

        content_type: str = "text",

        metadata: dict | None = None,

    ):

        artifact = (

            self.save_learning_artifact(

                session_id=(
                    session_id
                ),

                object_id=(
                    object_id
                ),

                action=action,

                content=content,

                title=title,

                content_type=(
                    content_type
                ),

                metadata=metadata,
            )
        )

        self.link_interaction_artifact(

            interaction_id,

            artifact,
        )

        return artifact
