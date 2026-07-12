from frontend.src.workspace import (
    create_visual_research_workspace,
)

from backend.session import (
    ArtifactRestorationResult,
    InMemoryInteractionArtifactLinkStore,
    InMemoryResearchArtifactStore,
    InMemoryResearchCheckpointStore,
    InMemoryResearchSessionStore,
    InMemoryResearchSessionVersionStore,
    InteractionArtifactCorrelationManager,
    ResearchArtifactManager,
    ResearchArtifactRestorer,
    ResearchArtifactTypeMapper,
    ResearchCheckpointManager,
    ResearchCheckpointReason,
    ResearchCheckpointRecoveryManager,
    ResearchRuntimeRegistry,
    ResearchRuntimeResolver,
    ResearchSessionManager,
    ResearchSessionRestorer,
    ResearchSessionSerializer,
    ResearchSessionVersionManager,
)


class PreReqAIApplication:
    """
    Application-level entry point
    for the visual PreReqAI experience.
    """

    def __init__(

        self,

        session_store=None,

        artifact_store=None,

        interaction_link_store=None,

        checkpoint_store=None,

        session_version_store=None,

    ):

        self.artifact_store = (

            artifact_store

            or InMemoryResearchArtifactStore()
        )

        self.artifact_manager = (
            ResearchArtifactManager(

                self.artifact_store
            )
        )

        self.artifact_restorer = (

            ResearchArtifactRestorer(

                self.artifact_store
            )
        )

        self.interaction_artifact_link_store = (

            interaction_link_store

            or (
                InMemoryInteractionArtifactLinkStore()
            )
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

            session_store

            or InMemoryResearchSessionStore()
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

        self.checkpoint_store = (

            checkpoint_store

            or InMemoryResearchCheckpointStore()
        )

        self.session_version_store = (

            session_version_store

            or (
                InMemoryResearchSessionVersionStore()
            )
        )

        self.session_version_manager = (

            ResearchSessionVersionManager(

                self.session_version_store
            )
        )

        self.checkpoint_manager = (

            ResearchCheckpointManager(

                session_manager=(
                    self.session_manager
                ),

                checkpoint_store=(
                    self.checkpoint_store
                ),

                version_manager=(
                    self.session_version_manager
                ),
            )
        )

        self.recovery_manager = (

            ResearchCheckpointRecoveryManager(

                checkpoint_manager=(
                    self.checkpoint_manager
                ),

                version_manager=(
                    self.session_version_manager
                ),

                session_restorer=(
                    self.session_restorer
                ),
            )
        )

        self.active_session_id = None

        self.active_paper_id = None

        self.active_paper_title = None

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

        self.checkpoint_active_session(

            ResearchCheckpointReason
            .ARTIFACT_CREATED,

            metadata={

                "interaction_id":
                    str(interaction_id),

                "artifact_id":
                    artifact.id,

                "object_id":
                    artifact.object_id,

                "action":
                    artifact.action,
            },
        )

        return artifact

    def restore_interaction_artifacts(

        self,

        interaction_id: str,

    ):

        links = (

            self
            .interaction_artifact_correlations
            .links_for_interaction(

                interaction_id
            )
        )

        artifact_ids = [

            link.artifact_id

            for link in links
        ]

        return (

            self.artifact_restorer
            .restore_for_interaction(

                interaction_id=(
                    interaction_id
                ),

                artifact_ids=(
                    artifact_ids
                ),

                workspace=(
                    self.workspace
                ),
            )
        )

    def restore_history_entry(

        self,

        entry_id: str,

    ):

        selected = (

            self.workspace
            .workspace
            .select_history_entry(

                entry_id
            )
        )

        if selected is None:

            return ArtifactRestorationResult(

                restored=False,

                interaction_id=(
                    entry_id
                ),
            )

        return (

            self.artifact_restorer
            .restore_for_interaction(

                interaction_id=(
                    selected.id
                ),

                artifact_ids=(

                    selected.artifact_ids
                ),

                workspace=(
                    self.workspace
                ),
            )
        )

    def activate_research_session(

        self,

        session_id: str,

        paper_id: str | None = None,

        paper_title: str | None = None,

    ):

        self.active_session_id = (
            session_id
        )

        self.active_paper_id = (
            paper_id
        )

        self.active_paper_title = (
            paper_title
        )

        return session_id

    def deactivate_research_session(

        self,

    ):

        session_id = (
            self.active_session_id
        )

        self.active_session_id = None

        self.active_paper_id = None

        self.active_paper_title = None

        return session_id

    def checkpoint_active_session(

        self,

        reason,

        metadata: dict | None = None,

    ):

        if self.active_session_id is None:

            return None

        return (

            self.checkpoint_manager
            .checkpoint(

                session_id=(
                    self.active_session_id
                ),

                workspace=(
                    self.workspace
                ),

                reason=reason,

                paper_id=(
                    self.active_paper_id
                ),

                paper_title=(
                    self.active_paper_title
                ),

                metadata=metadata,
            )
        )

    def checkpoint_workflow_progress(

        self,

        step_id: str | None = None,

    ):

        return (

            self.checkpoint_active_session(

                ResearchCheckpointReason
                .WORKFLOW_PROGRESS,

                metadata={

                    "step_id":
                        step_id,
                },
            )
        )

    def checkpoint_research_object(

        self,

        object_id: str,

    ):

        return (

            self.checkpoint_active_session(

                ResearchCheckpointReason
                .RESEARCH_OBJECT_CHANGED,

                metadata={

                    "object_id":
                        object_id,
                },
            )
        )

    def checkpoint_section(

        self,

        section_id: str,

    ):

        return (

            self.checkpoint_active_session(

                ResearchCheckpointReason
                .SECTION_CHANGED,

                metadata={

                    "section_id":
                        section_id,
                },
            )
        )

    def checkpoint_graph_context(

        self,

        node_id: str,

    ):

        return (

            self.checkpoint_active_session(

                ResearchCheckpointReason
                .GRAPH_CONTEXT_CHANGED,

                metadata={

                    "node_id":
                        node_id,
                },
            )
        )

    def checkpoint_before_background(

        self,

    ):

        return (

            self.checkpoint_active_session(

                ResearchCheckpointReason
                .APPLICATION_BACKGROUND
            )
        )

    def checkpoint_research_session(

        self,

    ):

        return (

            self.checkpoint_active_session(

                ResearchCheckpointReason
                .MANUAL
            )
        )

    def research_checkpoints(

        self,

        session_id: str,

    ):

        return (

            self.checkpoint_manager
            .list_checkpoints(

                session_id
            )
        )

    def latest_research_checkpoint(

        self,

        session_id: str,

    ):

        return (

            self.checkpoint_manager
            .latest_checkpoint(

                session_id
            )
        )

    def get_research_checkpoint(

        self,

        checkpoint_id: str,

    ):

        return (

            self.checkpoint_manager
            .get_checkpoint(

                checkpoint_id
            )
        )

    def delete_research_checkpoint(

        self,

        checkpoint_id: str,

    ):

        return (

            self.checkpoint_manager
            .delete_checkpoint(

                checkpoint_id
            )
        )

    def get_research_session_version(

        self,

        version_id: str,

    ):

        return (

            self.session_version_manager
            .get(

                version_id
            )
        )

    def research_session_versions(

        self,

        session_id: str,

    ):

        return (

            self.session_version_manager
            .for_session(

                session_id
            )
        )

    def latest_research_session_version(

        self,

        session_id: str,

    ):

        return (

            self.session_version_manager
            .latest(

                session_id
            )
        )

    def research_checkpoint_version(

        self,

        checkpoint_id: str,

    ):

        checkpoint = (

            self.get_research_checkpoint(

                checkpoint_id
            )
        )

        if checkpoint is None:

            return None

        if (

            checkpoint.snapshot_version_id

            is None
        ):

            return None

        return (

            self.get_research_session_version(

                checkpoint
                .snapshot_version_id
            )
        )

    def restore_research_checkpoint(

        self,

        checkpoint_id: str,

    ):

        if self.active_session_id is None:

            raise ValueError(

                "No active research session "
                "is available for recovery"
            )

        restored_workspace, result = (

            self.recovery_manager
            .recover(

                checkpoint_id=(
                    checkpoint_id
                ),

                current_workspace=(
                    self.workspace
                ),

                session_id=(
                    self.active_session_id
                ),

                paper_id=(
                    self.active_paper_id
                ),

                paper_title=(
                    self.active_paper_title
                ),
            )
        )

        self.workspace = (
            restored_workspace
        )

        source_version = (

            self.get_research_session_version(

                result.source_version_id
            )
        )

        if source_version is not None:

            self.active_paper_id = (

                source_version
                .snapshot
                .paper_id
            )

            self.active_paper_title = (

                source_version
                .snapshot
                .paper_title
            )

        return result
