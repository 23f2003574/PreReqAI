from frontend.src.workspace import (
    create_visual_research_workspace,
)

from backend.session import (
    AnnotatedResearchCheckpoint,
    ArtifactRestorationResult,
    InMemoryInteractionArtifactLinkStore,
    InMemoryResearchActivityStore,
    InMemoryResearchArtifactStore,
    InMemoryResearchCheckpointAnnotationStore,
    InMemoryResearchCheckpointStore,
    InMemoryResearchSessionStore,
    InMemoryResearchSessionVersionStore,
    InteractionArtifactCorrelationManager,
    normalize_research_tag_name,
    ResearchActivityActorType,
    ResearchActivityRecorder,
    ResearchActivityService,
    ResearchActivityType,
    ResearchArtifactManager,
    ResearchArtifactRestorer,
    ResearchArtifactTypeMapper,
    InMemoryResearchCollectionStore,
    InMemoryResearchSessionBranchStore,
    InMemoryResearchSessionProfileStore,
    InMemoryResearchTagStore,
    ResearchCheckpointAnnotationManager,
    ResearchCheckpointManager,
    ResearchCheckpointReason,
    ResearchCheckpointRecoveryManager,
    ResearchHistoryQuery,
    ResearchHistoryQueryService,
    ResearchRecoveryPreviewManager,
    ResearchRuntimeRegistry,
    ResearchRuntimeResolver,
    ResearchSessionBranchManager,
    ResearchSessionComparator,
    ResearchSessionLineageComparisonService,
    ResearchSessionLineageService,
    ResearchSessionManager,
    ResearchSessionProfileManager,
    ResearchSessionQuery,
    ResearchSessionQueryService,
    ResearchSessionRestorer,
    ResearchSessionStatus,
    ResearchSessionSerializer,
    ResearchSessionVersionManager,
    ResearchSnapshotImportPlanner,
    ResearchSnapshotImportService,
    ResearchSnapshotImportStrategy,
    ResearchSnapshotImportTransaction,
    ResearchSnapshotScope,
    ResearchSnapshotSerializer,
    ResearchSnapshotService,
    ResearchSnapshotValidator,
    ResearchWorkspaceChangeFeed,
    ResearchWorkspaceChangeOperation,
    ResearchWorkspaceEventBus,
    ResearchWorkspaceInsightsService,
    ResearchWorkspaceIntegrityAuditor,
    ResearchWorkspaceOrganizationService,
    ResearchWorkspaceRepairPlanner,
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

        checkpoint_annotation_store=None,

        session_branch_store=None,

        session_profile_store=None,

        tag_store=None,

        collection_store=None,

        activity_store=None,

        research_workspace_change_feed_storage_path=None,

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

        self.research_activity_store = (

            activity_store

            or InMemoryResearchActivityStore()
        )

        self.activity_recorder = (

            ResearchActivityRecorder(

                activity_store=(
                    self.research_activity_store
                )
            )
        )

        self.research_activity_service = (

            ResearchActivityService(

                activity_store=(
                    self.research_activity_store
                )
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

        self.session_comparator = (

            ResearchSessionComparator()
        )

        self.recovery_preview_manager = (

            ResearchRecoveryPreviewManager(

                checkpoint_manager=(
                    self.checkpoint_manager
                ),

                version_manager=(
                    self.session_version_manager
                ),

                session_manager=(
                    self.session_manager
                ),

                comparator=(
                    self.session_comparator
                ),
            )
        )

        self.checkpoint_annotation_store = (

            checkpoint_annotation_store

            or (
                InMemoryResearchCheckpointAnnotationStore()
            )
        )

        self.checkpoint_annotation_manager = (

            ResearchCheckpointAnnotationManager(

                checkpoint_store=(
                    self.checkpoint_store
                ),

                annotation_store=(
                    self.checkpoint_annotation_store
                ),
            )
        )

        self.research_history_query_service = (

            ResearchHistoryQueryService(

                checkpoint_store=(
                    self.checkpoint_store
                ),

                annotation_store=(
                    self.checkpoint_annotation_store
                ),
            )
        )

        self.session_branch_store = (

            session_branch_store

            or (
                InMemoryResearchSessionBranchStore()
            )
        )

        self.session_branch_manager = (

            ResearchSessionBranchManager(

                checkpoint_store=(
                    self.checkpoint_store
                ),

                checkpoint_manager=(
                    self.checkpoint_manager
                ),

                version_manager=(
                    self.session_version_manager
                ),

                session_manager=(
                    self.session_manager
                ),

                session_restorer=(
                    self.session_restorer
                ),

                branch_store=(
                    self.session_branch_store
                ),

                workspace_factory=(

                    lambda:
                        create_visual_research_workspace(

                            correlation_provider=(

                                self
                                .interaction_artifact_correlations
                            )
                        )
                ),
            )
        )

        self.session_lineage_service = (

            ResearchSessionLineageService(

                branch_store=(
                    self.session_branch_store
                )
            )
        )

        self.session_profile_store = (

            session_profile_store

            or (
                InMemoryResearchSessionProfileStore()
            )
        )

        self.session_profile_manager = (

            ResearchSessionProfileManager(

                profile_store=(
                    self.session_profile_store
                ),

                session_manager=(
                    self.session_manager
                ),

                activity_recorder=(
                    self.activity_recorder
                ),
            )
        )

        self.tag_store = (

            tag_store

            or InMemoryResearchTagStore()
        )

        self.collection_store = (

            collection_store

            or (
                InMemoryResearchCollectionStore()
            )
        )

        self.session_query_service = (

            ResearchSessionQueryService(

                session_manager=(
                    self.session_manager
                ),

                profile_store=(
                    self.session_profile_store
                ),

                branch_store=(
                    self.session_branch_store
                ),

                lineage_service=(
                    self.session_lineage_service
                ),

                tag_store=(
                    self.tag_store
                ),

                collection_store=(
                    self.collection_store
                ),
            )
        )

        self.workspace_organization_service = (

            ResearchWorkspaceOrganizationService(

                session_manager=(
                    self.session_manager
                ),

                tag_store=(
                    self.tag_store
                ),

                collection_store=(
                    self.collection_store
                ),

                activity_recorder=(
                    self.activity_recorder
                ),
            )
        )

        self.session_lineage_comparison_service = (

            ResearchSessionLineageComparisonService(

                session_manager=(
                    self.session_manager
                ),

                branch_store=(
                    self.session_branch_store
                ),

                lineage_service=(
                    self.session_lineage_service
                ),

                artifact_store=(
                    self.artifact_store
                ),
            )
        )

        self.research_workspace_insights_service = (

            ResearchWorkspaceInsightsService(

                session_manager=(
                    self.session_manager
                ),

                profile_store=(
                    self.session_profile_store
                ),

                lineage_service=(
                    self.session_lineage_service
                ),

                tag_store=(
                    self.tag_store
                ),

                collection_store=(
                    self.collection_store
                ),

                activity_store=(
                    self.research_activity_store
                ),
            )
        )

        self.research_snapshot_validator = (

            ResearchSnapshotValidator()
        )

        self.research_snapshot_service = (

            ResearchSnapshotService(

                session_manager=(
                    self.session_manager
                ),

                profile_store=(
                    self.session_profile_store
                ),

                checkpoint_store=(
                    self.checkpoint_store
                ),

                version_store=(
                    self.session_version_store
                ),

                branch_store=(
                    self.session_branch_store
                ),

                lineage_service=(
                    self.session_lineage_service
                ),

                tag_store=(
                    self.tag_store
                ),

                collection_store=(
                    self.collection_store
                ),

                activity_store=(
                    self.research_activity_store
                ),

                validator=(
                    self.research_snapshot_validator
                ),
            )
        )

        self.research_snapshot_serializer = (

            ResearchSnapshotSerializer()
        )

        self.research_snapshot_import_planner = (

            ResearchSnapshotImportPlanner(

                session_manager=(
                    self.session_manager
                ),

                checkpoint_store=(
                    self.checkpoint_store
                ),

                version_store=(
                    self.session_version_store
                ),

                branch_store=(
                    self.session_branch_store
                ),

                tag_store=(
                    self.tag_store
                ),

                collection_store=(
                    self.collection_store
                ),

                activity_store=(
                    self.research_activity_store
                ),

                snapshot_validator=(
                    self.research_snapshot_validator
                ),
            )
        )

        self.research_snapshot_import_service = (

            ResearchSnapshotImportService(

                import_planner=(

                    self
                    .research_snapshot_import_planner
                ),

                transaction_factory=(

                    self
                    ._create_research_import_transaction
                ),

                session_manager=(
                    self.session_manager
                ),

                profile_store=(
                    self.session_profile_store
                ),

                checkpoint_store=(
                    self.checkpoint_store
                ),

                version_store=(
                    self.session_version_store
                ),

                branch_store=(
                    self.session_branch_store
                ),

                tag_store=(
                    self.tag_store
                ),

                collection_store=(
                    self.collection_store
                ),

                activity_store=(
                    self.research_activity_store
                ),
            )
        )

        self.research_workspace_integrity_auditor = (

            ResearchWorkspaceIntegrityAuditor(

                session_manager=(
                    self.session_manager
                ),

                profile_store=(
                    self.session_profile_store
                ),

                checkpoint_store=(
                    self.checkpoint_store
                ),

                version_store=(
                    self.session_version_store
                ),

                branch_store=(
                    self.session_branch_store
                ),

                tag_store=(
                    self.tag_store
                ),

                collection_store=(
                    self.collection_store
                ),

                activity_store=(
                    self.research_activity_store
                ),
            )
        )

        self.research_workspace_repair_planner = (

            ResearchWorkspaceRepairPlanner()
        )

        self.research_workspace_event_bus = (

            ResearchWorkspaceEventBus()
        )

        self.research_workspace_change_feed = (

            ResearchWorkspaceChangeFeed(

                storage_path=(

                    research_workspace_change_feed_storage_path
                ),

                event_bus=(

                    self
                    .research_workspace_event_bus
                ),
            )
        )

        self.active_session_id = None

        self.active_paper_id = None

        self.active_paper_title = None

    def _record_workspace_change(

        self,

        operation,

        entity_type,

        entity_id=None,

        related_entity_ids=None,

        metadata=None,

    ):

        return (

            self.research_workspace_change_feed
            .append(

                operation=(
                    operation
                ),

                entity_type=(
                    entity_type
                ),

                entity_id=(
                    entity_id
                ),

                related_entity_ids=(

                    related_entity_ids
                ),

                metadata=(
                    metadata
                ),
            )
        )

    def subscribe_to_research_workspace_changes(

        self,

        callback,

        entity_types=None,

        operations=None,

    ):

        return (

            self.research_workspace_event_bus
            .subscribe(

                callback=(
                    callback
                ),

                entity_types=(
                    entity_types
                ),

                operations=(
                    operations
                ),
            )
        )

    def unsubscribe_from_research_workspace_changes(

        self,

        subscription_id,

    ):

        return (

            self.research_workspace_event_bus
            .unsubscribe(

                subscription_id
            )
        )

    def get_research_workspace_changes(

        self,

        after_sequence=0,

        limit=100,

        entity_types=None,

        operations=None,

    ):

        return (

            self.research_workspace_change_feed
            .get_changes(

                after_sequence=(
                    after_sequence
                ),

                limit=limit,

                entity_types=(
                    entity_types
                ),

                operations=(
                    operations
                ),
            )
        )

    def get_latest_research_workspace_change_sequence(

        self,

    ):

        return (

            self.research_workspace_change_feed
            .latest_sequence
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

        existing = (

            self.session_manager
            .load_session(

                session_id
            )
        )

        self.active_session_id = (
            session_id
        )

        self.active_paper_id = (
            paper_id
        )

        self.active_paper_title = (
            paper_title
        )

        if existing is None:

            self.activity_recorder.record(

                ResearchActivityType
                .SESSION_CREATED,

                session_id=session_id,

                actor_type=(

                    ResearchActivityActorType
                    .USER
                ),
            )

            self._record_workspace_change(

                operation=(

                    ResearchWorkspaceChangeOperation
                    .CREATED
                ),

                entity_type=(
                    "session"
                ),

                entity_id=(
                    session_id
                ),
            )

        self.activity_recorder.record(

            ResearchActivityType
            .SESSION_ACTIVATED,

            session_id=session_id,

            actor_type=(

                ResearchActivityActorType
                .USER
            ),
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

        checkpoint = (

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

        if checkpoint is not None:

            self._record_workspace_change(

                operation=(

                    ResearchWorkspaceChangeOperation
                    .CREATED
                ),

                entity_type=(
                    "checkpoint"
                ),

                entity_id=(
                    checkpoint.id
                ),

                related_entity_ids=[

                    checkpoint.session_id
                ],
            )

        return checkpoint

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

        checkpoint = (

            self.checkpoint_active_session(

                ResearchCheckpointReason
                .MANUAL
            )
        )

        if checkpoint is not None:

            self.activity_recorder.record(

                ResearchActivityType
                .CHECKPOINT_CREATED,

                session_id=(
                    checkpoint.session_id
                ),

                actor_type=(

                    ResearchActivityActorType
                    .USER
                ),

                metadata={

                    "checkpoint_id":
                        checkpoint.id,
                },
            )

            if (

                checkpoint
                .snapshot_version_id

                is not None
            ):

                self.activity_recorder.record(

                    ResearchActivityType
                    .VERSION_CREATED,

                    session_id=(
                        checkpoint.session_id
                    ),

                    actor_type=(

                        ResearchActivityActorType
                        .SYSTEM
                    ),

                    metadata={

                        "version_id":
                            checkpoint
                            .snapshot_version_id,

                        "checkpoint_id":
                            checkpoint.id,
                    },
                )

        return checkpoint

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

    def preview_research_checkpoint_recovery(

        self,

        checkpoint_id: str,

    ):

        if self.active_session_id is None:

            raise ValueError(

                "No active research session "
                "is available for recovery "
                "preview"
            )

        return (

            self.recovery_preview_manager
            .preview(

                checkpoint_id=(
                    checkpoint_id
                ),

                session_id=(
                    self.active_session_id
                ),

                current_workspace=(
                    self.workspace
                ),

                paper_id=(
                    self.active_paper_id
                ),

                paper_title=(
                    self.active_paper_title
                ),
            )
        )

    def compare_research_session_versions(

        self,

        first_version_id: str,

        second_version_id: str,

    ):

        first = (

            self.get_research_session_version(

                first_version_id
            )
        )

        second = (

            self.get_research_session_version(

                second_version_id
            )
        )

        if first is None:

            raise ValueError(

                "Research session version "
                "does not exist: "
                f"{first_version_id}"
            )

        if second is None:

            raise ValueError(

                "Research session version "
                "does not exist: "
                f"{second_version_id}"
            )

        if (

            first.session_id

            != second.session_id
        ):

            raise ValueError(

                "Research session versions "
                "belong to different sessions"
            )

        return (

            self.session_comparator
            .compare(

                current_snapshot=(
                    first.snapshot
                ),

                target_snapshot=(
                    second.snapshot
                ),
            )
        )

    def update_research_checkpoint_annotation(

        self,

        checkpoint_id: str,

        **changes,

    ):

        return (

            self.checkpoint_annotation_manager
            .update(

                checkpoint_id,

                **changes,
            )
        )

    def research_checkpoint_annotation(

        self,

        checkpoint_id: str,

    ):

        return (

            self.checkpoint_annotation_manager
            .get(

                checkpoint_id
            )
        )

    def remove_research_checkpoint_annotation(

        self,

        checkpoint_id: str,

    ):

        return (

            self.checkpoint_annotation_manager
            .remove(

                checkpoint_id
            )
        )

    def annotated_research_checkpoints(

        self,

        session_id: str,

    ):

        checkpoints = (

            self.research_checkpoints(

                session_id
            )
        )

        return [

            AnnotatedResearchCheckpoint(

                checkpoint=checkpoint,

                annotation=(

                    self
                    .research_checkpoint_annotation(

                        checkpoint.id
                    )
                ),
            )

            for checkpoint

            in checkpoints
        ]

    def pinned_research_checkpoints(

        self,

        session_id: str,

    ):

        return [

            checkpoint

            for checkpoint

            in (
                self
                .annotated_research_checkpoints(

                    session_id
                )
            )

            if checkpoint.pinned
        ]

    def label_research_checkpoint(

        self,

        checkpoint_id: str,

        label: str | None,

    ):

        return (

            self
            .update_research_checkpoint_annotation(

                checkpoint_id,

                label=label,
            )
        )

    def note_research_checkpoint(

        self,

        checkpoint_id: str,

        note: str | None,

    ):

        return (

            self
            .update_research_checkpoint_annotation(

                checkpoint_id,

                note=note,
            )
        )

    def pin_research_checkpoint(

        self,

        checkpoint_id: str,

    ):

        return (

            self
            .update_research_checkpoint_annotation(

                checkpoint_id,

                pinned=True,
            )
        )

    def unpin_research_checkpoint(

        self,

        checkpoint_id: str,

    ):

        return (

            self
            .update_research_checkpoint_annotation(

                checkpoint_id,

                pinned=False,
            )
        )

    def query_research_history(

        self,

        session_id: str,

        reasons=None,

        pinned=None,

        recovery_only=False,

        search=None,

        created_from=None,

        created_until=None,

        sort_order="newest",

        offset=0,

        limit=50,

    ):

        query = ResearchHistoryQuery(

            reasons=set(
                reasons or []
            ),

            pinned=pinned,

            recovery_only=(
                recovery_only
            ),

            search=search,

            created_from=(
                created_from
            ),

            created_until=(
                created_until
            ),

            sort_order=(
                sort_order
            ),

            offset=offset,

            limit=limit,
        )

        return (

            self.research_history_query_service
            .query(

                session_id=(
                    session_id
                ),

                query=query,
            )
        )

    def query_active_research_history(

        self,

        **query_options,

    ):

        if self.active_session_id is None:

            raise ValueError(

                "No active research session "
                "is available"
            )

        return (

            self.query_research_history(

                session_id=(
                    self.active_session_id
                ),

                **query_options,
            )
        )

    def branch_research_checkpoint(

        self,

        checkpoint_id: str,

        branch_session_id:
            str | None = None,

        display_name:
            str | None = None,

        description:
            str | None = None,

        metadata:
            dict | None = None,

    ):

        (
            branch,
            initial_checkpoint,
            restored_workspace,

        ) = (

            self.session_branch_manager
            .create_from_checkpoint(

                checkpoint_id=(
                    checkpoint_id
                ),

                branch_session_id=(
                    branch_session_id
                ),

                metadata=metadata,
            )
        )

        profile = (

            self.session_profile_manager
            .get_or_create(

                session_id=(

                    branch
                    .branch_session_id
                ),

                display_name=(
                    display_name
                ),

                description=(
                    description
                ),
            )
        )

        self.activity_recorder.record(

            ResearchActivityType
            .BRANCH_CREATED,

            session_id=(
                branch.source_session_id
            ),

            related_session_id=(
                branch.branch_session_id
            ),

            actor_type=(

                ResearchActivityActorType
                .USER
            ),

            metadata={

                "branch_session_id":
                    branch.branch_session_id,

                "source_checkpoint_id":
                    branch
                    .source_checkpoint_id,

                "source_version_id":
                    branch.source_version_id,
            },
        )

        self._record_workspace_change(

            operation=(

                ResearchWorkspaceChangeOperation
                .CREATED
            ),

            entity_type=(
                "session"
            ),

            entity_id=(
                branch.branch_session_id
            ),
        )

        self._record_workspace_change(

            operation=(

                ResearchWorkspaceChangeOperation
                .CREATED
            ),

            entity_type=(
                "branch"
            ),

            related_entity_ids=[

                branch.source_session_id,

                branch.branch_session_id,
            ],
        )

        return {

            "branch":
                branch,

            "initial_checkpoint":
                initial_checkpoint,

            "workspace":
                restored_workspace,

            "profile":
                profile,
        }

    def branch_and_activate_research_checkpoint(

        self,

        checkpoint_id: str,

        branch_session_id:
            str | None = None,

        metadata:
            dict | None = None,

    ):

        result = (

            self.branch_research_checkpoint(

                checkpoint_id=(
                    checkpoint_id
                ),

                branch_session_id=(
                    branch_session_id
                ),

                metadata=metadata,
            )
        )

        branch = result[
            "branch"
        ]

        version = (

            self.get_research_session_version(

                branch.source_version_id
            )
        )

        self.active_session_id = (
            branch.branch_session_id
        )

        self.workspace = (
            result["workspace"]
        )

        if version is not None:

            self.active_paper_id = (

                version
                .snapshot
                .paper_id
            )

            self.active_paper_title = (

                version
                .snapshot
                .paper_title
            )

        return result

    def research_session_branch_origin(

        self,

        session_id: str,

    ):

        return (

            self.session_branch_store
            .get_by_branch_session(

                session_id
            )
        )

    def research_session_branches(

        self,

        session_id: str,

    ):

        return (

            self.session_branch_store
            .list_from_session(

                session_id
            )
        )

    def research_checkpoint_branches(

        self,

        checkpoint_id: str,

    ):

        return (

            self.session_branch_store
            .list_from_checkpoint(

                checkpoint_id
            )
        )

    def research_session_parent(

        self,

        session_id: str,

    ):

        return (

            self.session_lineage_service
            .parent_session_id(

                session_id
            )
        )

    def research_session_children(

        self,

        session_id: str,

    ):

        return (

            self.session_lineage_service
            .child_session_ids(

                session_id
            )
        )

    def research_session_ancestors(

        self,

        session_id: str,

    ):

        return (

            self.session_lineage_service
            .ancestor_session_ids(

                session_id
            )
        )

    def research_session_descendants(

        self,

        session_id: str,

    ):

        return (

            self.session_lineage_service
            .descendant_session_ids(

                session_id
            )
        )

    def research_session_root(

        self,

        session_id: str,

    ):

        return (

            self.session_lineage_service
            .root_session_id(

                session_id
            )
        )

    def research_session_depth(

        self,

        session_id: str,

    ):

        return (

            self.session_lineage_service
            .depth(

                session_id
            )
        )

    def research_sessions_are_related(

        self,

        first_session_id: str,

        second_session_id: str,

    ):

        return (

            self.session_lineage_service
            .are_related(

                first_session_id,

                second_session_id,
            )
        )

    def research_session_is_ancestor(

        self,

        ancestor_session_id: str,

        descendant_session_id: str,

    ):

        return (

            self.session_lineage_service
            .is_ancestor(

                ancestor_session_id,

                descendant_session_id,
            )
        )

    def research_session_lowest_common_ancestor(

        self,

        first_session_id: str,

        second_session_id: str,

    ):

        return (

            self.session_lineage_service
            .lowest_common_ancestor(

                first_session_id,

                second_session_id,
            )
        )

    def research_session_path_from_root(

        self,

        session_id: str,

    ):

        return (

            self.session_lineage_service
            .path_from_root(

                session_id
            )
        )

    def research_session_path_between(

        self,

        first_session_id: str,

        second_session_id: str,

    ):

        return (

            self.session_lineage_service
            .path_between(

                first_session_id,

                second_session_id,
            )
        )

    def _enrich_lineage_node(

        self,

        node,

    ):

        profile = (

            self.research_session_profile(

                node.session_id
            )
        )

        node.display_name = (

            self.research_session_display_name(

                node.session_id
            )
        )

        if profile is not None:

            node.description = (
                profile.description
            )

            node.status = (
                profile.status.value
            )

            node.archived = (
                profile.archived
            )

        for child in node.children:

            self._enrich_lineage_node(
                child
            )

        return node

    def research_session_lineage_tree(

        self,

        session_id: str,

    ):

        tree = (

            self.session_lineage_service
            .lineage_tree(

                session_id
            )
        )

        return (

            self._enrich_lineage_node(

                tree
            )
        )

    def research_session_lineage_summary(

        self,

        session_id: str,

    ):

        return (

            self.session_lineage_service
            .summarize(

                session_id
            )
        )

    def research_session_profile(

        self,

        session_id: str,

    ):

        return (

            self.session_profile_store
            .get(

                session_id
            )
        )

    def update_research_session_profile(

        self,

        session_id: str,

        **changes,

    ):

        profile = (

            self.session_profile_manager
            .update(

                session_id=(
                    session_id
                ),

                **changes,
            )
        )

        self._record_workspace_change(

            operation=(

                ResearchWorkspaceChangeOperation
                .UPDATED
            ),

            entity_type=(
                "session_profile"
            ),

            entity_id=(
                profile.session_id
            ),

            related_entity_ids=[

                profile.session_id
            ],
        )

        return profile

    def research_session_display_name(

        self,

        session_id: str,

    ):

        return (

            self.session_profile_manager
            .display_name(

                session_id
            )
        )

    def _record_lifecycle_change(

        self,

        session_id,

        previous_profile,

        updated_profile,

    ):

        self._record_workspace_change(

            operation=(

                ResearchWorkspaceChangeOperation
                .UPDATED
            ),

            entity_type=(
                "session"
            ),

            entity_id=(
                session_id
            ),

            metadata={

                "change":
                    "lifecycle_state",

                "previous_state":
                    (

                        previous_profile
                        .status
                        .value

                        if previous_profile
                        is not None

                        else (

                            ResearchSessionStatus
                            .ACTIVE
                            .value
                        )
                    ),

                "current_state":
                    updated_profile
                    .status
                    .value,
            },
        )

    def pause_research_session(

        self,

        session_id: str,

    ):

        previous_profile = (

            self.research_session_profile(

                session_id
            )
        )

        updated_profile = (

            self.session_profile_manager
            .pause(

                session_id
            )
        )

        self._record_lifecycle_change(

            session_id,

            previous_profile,

            updated_profile,
        )

        return updated_profile

    def resume_research_session(

        self,

        session_id: str,

    ):

        previous_profile = (

            self.research_session_profile(

                session_id
            )
        )

        updated_profile = (

            self.session_profile_manager
            .resume(

                session_id
            )
        )

        self._record_lifecycle_change(

            session_id,

            previous_profile,

            updated_profile,
        )

        return updated_profile

    def complete_research_session(

        self,

        session_id: str,

    ):

        previous_profile = (

            self.research_session_profile(

                session_id
            )
        )

        updated_profile = (

            self.session_profile_manager
            .complete(

                session_id
            )
        )

        self._record_lifecycle_change(

            session_id,

            previous_profile,

            updated_profile,
        )

        return updated_profile

    def archive_research_session(

        self,

        session_id: str,

    ):

        return (

            self.session_profile_manager
            .archive(

                session_id
            )
        )

    def unarchive_research_session(

        self,

        session_id: str,

    ):

        return (

            self.session_profile_manager
            .unarchive(

                session_id
            )
        )

    def query_research_sessions(

        self,

        search=None,

        statuses=None,

        archived=None,

        kinds=None,

        lineage_root_session_id=None,

        direct_parent_session_id=None,

        tag_names=None,

        match_all_tags=True,

        collection_ids=None,

        sort_order="updated_newest",

        offset=0,

        limit=50,

    ):

        query = (

            ResearchSessionQuery(

                search=search,

                statuses=set(
                    statuses or []
                ),

                archived=archived,

                kinds=set(
                    kinds or []
                ),

                lineage_root_session_id=(

                    lineage_root_session_id
                ),

                direct_parent_session_id=(

                    direct_parent_session_id
                ),

                tag_names=set(
                    tag_names or []
                ),

                match_all_tags=(
                    match_all_tags
                ),

                collection_ids=set(
                    collection_ids or []
                ),

                sort_order=(
                    sort_order
                ),

                offset=offset,

                limit=limit,
            )
        )

        return (

            self.session_query_service
            .query(

                query
            )
        )

    def active_research_sessions(

        self,

        **query_options,

    ):

        options = {

            **query_options,

            "archived": False,
        }

        return self.query_research_sessions(
            **options
        )

    def archived_research_sessions(

        self,

        **query_options,

    ):

        options = {

            **query_options,

            "archived": True,
        }

        return self.query_research_sessions(
            **options
        )

    def root_research_sessions(

        self,

        **query_options,

    ):

        options = {

            **query_options,

            "kinds": {
                "root"
            },
        }

        return self.query_research_sessions(
            **options
        )

    def compare_research_sessions(

        self,

        first_session_id: str,

        second_session_id: str,

    ):

        comparison = (

            self.session_lineage_comparison_service
            .compare(

                first_session_id=(
                    first_session_id
                ),

                second_session_id=(
                    second_session_id
                ),
            )
        )

        self.activity_recorder.record(

            ResearchActivityType
            .SESSION_COMPARED,

            session_id=first_session_id,

            related_session_id=(
                second_session_id
            ),

            actor_type=(

                ResearchActivityActorType
                .USER
            ),

            metadata={

                "relationship":
                    comparison
                    .relationship
                    .value,

                "lineage_distance":
                    comparison
                    .lineage_distance,
            },
        )

        return comparison

    def tag_research_session(

        self,

        session_id,

        tag_name,

    ):

        existing_tag_ids = {

            assignment.tag_id

            for assignment

            in (

                self.tag_store
                .list_assignments_for_session(

                    session_id
                )
            )
        }

        tag = (

            self.workspace_organization_service
            .tag_session(

                session_id,

                tag_name,
            )
        )

        if tag.id not in existing_tag_ids:

            self._record_workspace_change(

                operation=(

                    ResearchWorkspaceChangeOperation
                    .CREATED
                ),

                entity_type=(
                    "tag_assignment"
                ),

                related_entity_ids=[

                    session_id,

                    tag.id,
                ],
            )

        return tag

    def untag_research_session(

        self,

        session_id,

        tag_name,

    ):

        existing_tag = (

            self.tag_store
            .get_tag_by_name(

                normalize_research_tag_name(

                    tag_name
                )
            )
        )

        removed = (

            self.workspace_organization_service
            .untag_session(

                session_id,

                tag_name,
            )
        )

        if (

            removed

            and existing_tag is not None
        ):

            self._record_workspace_change(

                operation=(

                    ResearchWorkspaceChangeOperation
                    .DELETED
                ),

                entity_type=(
                    "tag_assignment"
                ),

                related_entity_ids=[

                    session_id,

                    existing_tag.id,
                ],
            )

        return removed

    def research_session_tags(

        self,

        session_id,

    ):

        return (

            self.workspace_organization_service
            .tags_for_session(

                session_id
            )
        )

    def create_research_collection(

        self,

        name,

        description=None,

    ):

        return (

            self.workspace_organization_service
            .create_collection(

                name,

                description,
            )
        )

    def update_research_collection(

        self,

        collection_id,

        name=None,

        description=None,

    ):

        return (

            self.workspace_organization_service
            .update_collection(

                collection_id,

                name=name,

                description=description,
            )
        )

    def add_research_session_to_collection(

        self,

        collection_id,

        session_id,

    ):

        existing_session_ids = set(

            self.collection_store
            .list_session_ids(

                collection_id
            )
        )

        membership = (

            self.workspace_organization_service
            .add_session_to_collection(

                collection_id,

                session_id,
            )
        )

        if (

            session_id

            not in existing_session_ids
        ):

            self._record_workspace_change(

                operation=(

                    ResearchWorkspaceChangeOperation
                    .CREATED
                ),

                entity_type=(
                    "collection_membership"
                ),

                related_entity_ids=[

                    collection_id,

                    session_id,
                ],
            )

        return membership

    def remove_research_session_from_collection(

        self,

        collection_id,

        session_id,

    ):

        removed = (

            self.workspace_organization_service
            .remove_session_from_collection(

                collection_id,

                session_id,
            )
        )

        if removed:

            self._record_workspace_change(

                operation=(

                    ResearchWorkspaceChangeOperation
                    .DELETED
                ),

                entity_type=(
                    "collection_membership"
                ),

                related_entity_ids=[

                    collection_id,

                    session_id,
                ],
            )

        return removed

    def delete_research_collection(

        self,

        collection_id,

    ):

        return (

            self.workspace_organization_service
            .delete_collection(

                collection_id
            )
        )

    def research_collections_for_session(

        self,

        session_id,

    ):

        return (

            self.workspace_organization_service
            .collections_for_session(

                session_id
            )
        )

    def research_session_ids_in_collection(

        self,

        collection_id,

    ):

        return (

            self.workspace_organization_service
            .session_ids_in_collection(

                collection_id
            )
        )

    def research_session_activity(

        self,

        session_id,

        page=1,

        page_size=50,

    ):

        return (

            self.research_activity_service
            .timeline_for_session(

                session_id=(
                    session_id
                ),

                page=page,

                page_size=(
                    page_size
                ),
            )
        )

    def recent_research_activity(

        self,

        page=1,

        page_size=50,

    ):

        return (

            self.research_activity_service
            .recent_activity(

                page=page,

                page_size=(
                    page_size
                ),
            )
        )

    def query_research_activity(

        self,

        query,

    ):

        return (

            self.research_activity_service
            .query(

                query
            )
        )

    def research_workspace_insights(

        self,

        top_tag_limit=10,

        collection_limit=10,

        recent_session_limit=10,

        dormant_session_limit=10,

        dormant_after_days=30,

    ):

        return (

            self.research_workspace_insights_service
            .build_insights(

                top_tag_limit=(
                    top_tag_limit
                ),

                collection_limit=(
                    collection_limit
                ),

                recent_session_limit=(
                    recent_session_limit
                ),

                dormant_session_limit=(
                    dormant_session_limit
                ),

                dormant_after_days=(
                    dormant_after_days
                ),
            )
        )

    def export_research_session(

        self,

        session_id,

    ):

        return (

            self.research_snapshot_service
            .build_snapshot(

                scope=(

                    ResearchSnapshotScope
                    .SESSION
                ),

                root_session_id=(
                    session_id
                ),
            )
        )

    def export_research_session_tree(

        self,

        session_id,

    ):

        return (

            self.research_snapshot_service
            .build_snapshot(

                scope=(

                    ResearchSnapshotScope
                    .SESSION_WITH_DESCENDANTS
                ),

                root_session_id=(
                    session_id
                ),
            )
        )

    def export_research_lineage(

        self,

        session_id,

    ):

        return (

            self.research_snapshot_service
            .build_snapshot(

                scope=(

                    ResearchSnapshotScope
                    .LINEAGE
                ),

                root_session_id=(
                    session_id
                ),
            )
        )

    def export_research_workspace(

        self,

    ):

        return (

            self.research_snapshot_service
            .build_snapshot(

                scope=(

                    ResearchSnapshotScope
                    .WORKSPACE
                )
            )
        )

    def serialize_research_snapshot(

        self,

        snapshot,

    ):

        return (

            self.research_snapshot_serializer
            .dumps(
                snapshot
            )
        )

    def write_research_snapshot(

        self,

        snapshot,

        path,

    ):

        return (

            self.research_snapshot_serializer
            .write(

                snapshot,

                path,
            )
        )

    def _create_research_import_transaction(

        self,

    ):

        return (

            ResearchSnapshotImportTransaction(

                stores=[

                    self.session_manager,

                    self.session_profile_store,

                    self.checkpoint_store,

                    self.session_version_store,

                    self.session_branch_store,

                    self.tag_store,

                    self.collection_store,

                    self.research_activity_store,
                ]
            )
        )

    def preview_research_snapshot_import(

        self,

        snapshot,

        strategy=(

            ResearchSnapshotImportStrategy
            .REJECT
        ),

    ):

        return (

            self.research_snapshot_import_service
            .preview(

                snapshot=snapshot,

                strategy=strategy,
            )
        )

    def import_research_snapshot(

        self,

        snapshot,

        strategy=(

            ResearchSnapshotImportStrategy
            .REJECT
        ),

    ):

        result = (

            self.research_snapshot_import_service
            .import_snapshot(

                snapshot=snapshot,

                strategy=strategy,
            )
        )

        self._record_workspace_change(

            operation=(

                ResearchWorkspaceChangeOperation
                .IMPORTED
            ),

            entity_type=(
                "workspace_snapshot"
            ),

            entity_id=(
                result.snapshot_id
            ),

            metadata={

                "imported_sessions":
                    result
                    .imported_sessions,

                "imported_checkpoints":
                    result
                    .imported_checkpoints,

                "imported_versions":
                    result
                    .imported_versions,

                "imported_branches":
                    result
                    .imported_branches,

                "imported_tags":
                    result
                    .imported_tags,

                "imported_collections":
                    result
                    .imported_collections,

                "imported_activity_events":
                    result
                    .imported_activity_events,
            },
        )

        return result

    def import_research_snapshot_json(

        self,

        payload,

        strategy=(

            ResearchSnapshotImportStrategy
            .REJECT
        ),

    ):

        snapshot = (

            self.research_snapshot_serializer
            .loads(
                payload
            )
        )

        return (

            self.import_research_snapshot(

                snapshot=snapshot,

                strategy=strategy,
            )
        )

    def audit_research_workspace(

        self,

    ):

        return (

            self.research_workspace_integrity_auditor
            .audit()
        )

    def plan_research_workspace_repairs(

        self,

        report=None,

    ):

        if report is None:

            report = (

                self.audit_research_workspace()
            )

        return (

            self.research_workspace_repair_planner
            .plan(
                report
            )
        )
