from .tutor_mode import (
    TutorMode,
)

from .learning_intent import (
    LearningIntent,
)

from .workflow_type import (
    WorkflowType,
)

from .workflow_memory import (
    WorkflowMemory,
    WorkflowRecord,
)

from .learning_gap import (
    LearningGap,
)

from .learning_recommendation import (
    LearningRecommendation,
)

from .learning_session import (
    LearningSession,
)

from .session_manager import (
    SessionManager,
)

from .learning_question import (
    LearningQuestion,
)

from .question_manager import (
    QuestionManager,
)

from .context_retriever import (
    RetrievedContext,
    ContextRetriever,
)

from .context_manager import (
    ContextManager,
)

from .research_session_snapshot import (
    ResearchSessionSnapshot,
)

from .research_session_serializer import (
    ResearchSessionSerializer,
)

from .research_session_store import (
    ResearchSessionStore,
)

from .in_memory_research_session_store import (
    InMemoryResearchSessionStore,
)

from .research_session_manager import (
    ResearchSessionManager,
)

from .research_runtime_registry import (
    ResearchRuntimeRegistry,
)

from .research_runtime_resolver import (
    ResearchRuntimeResolver,
)

from .research_session_restoration_result import (
    ResearchSessionRestorationResult,
)

from .research_session_restorer import (
    ResearchSessionRestorer,
)

from .research_artifact_type import (
    ResearchArtifactType,
)

from .research_artifact import (
    ResearchArtifact,
)

from .research_artifact_store import (
    ResearchArtifactStore,
)

from .in_memory_research_artifact_store import (
    InMemoryResearchArtifactStore,
)

from .research_artifact_manager import (
    ResearchArtifactManager,
)

from .research_artifact_type_mapper import (
    ResearchArtifactTypeMapper,
)

from .interaction_artifact_link import (
    InteractionArtifactLink,
)

from .interaction_artifact_link_store import (
    InteractionArtifactLinkStore,
)

from .in_memory_interaction_artifact_link_store import (
    InMemoryInteractionArtifactLinkStore,
)

from .interaction_artifact_correlation_manager import (
    InteractionArtifactCorrelationManager,
)

from .artifact_restoration_result import (
    ArtifactRestorationResult,
)

from .research_artifact_restorer import (
    ResearchArtifactRestorer,
)

from .research_checkpoint_reason import (
    ResearchCheckpointReason,
)

from .research_checkpoint import (
    ResearchCheckpoint,
)

from .research_checkpoint_policy import (
    ResearchCheckpointPolicy,
)

from .research_checkpoint_manager import (
    ResearchCheckpointManager,
)

from .json_research_session_store import (
    JsonResearchSessionStore,
)

from .json_research_artifact_store import (
    JsonResearchArtifactStore,
)

from .json_interaction_artifact_link_store import (
    JsonInteractionArtifactLinkStore,
)

from .research_persistence_config import (
    ResearchPersistenceConfig,
)

from .research_persistence_factory import (
    ResearchPersistenceFactory,
)

from .research_checkpoint_store import (
    ResearchCheckpointStore,
)

from .in_memory_research_checkpoint_store import (
    InMemoryResearchCheckpointStore,
)

from .json_research_checkpoint_store import (
    JsonResearchCheckpointStore,
)

from .research_session_version import (
    ResearchSessionVersion,
)

from .research_session_version_store import (
    ResearchSessionVersionStore,
)

from .in_memory_research_session_version_store import (
    InMemoryResearchSessionVersionStore,
)

from .json_research_session_version_store import (
    JsonResearchSessionVersionStore,
)

from .research_session_version_manager import (
    ResearchSessionVersionManager,
)

from .research_recovery_result import (
    ResearchRecoveryResult,
)

from .research_checkpoint_recovery_manager import (
    ResearchCheckpointRecoveryManager,
)

from .research_state_change_type import (
    ResearchStateChangeType,
)

from .research_state_change import (
    ResearchStateChange,
)

from .research_session_comparison import (
    ResearchSessionComparison,
)

from .research_session_comparator import (
    ResearchSessionComparator,
)

from .research_recovery_preview import (
    ResearchRecoveryPreview,
)

from .research_recovery_preview_manager import (
    ResearchRecoveryPreviewManager,
)

from .unset import (
    UNSET,
)

from .research_checkpoint_annotation import (
    ResearchCheckpointAnnotation,
)

from .research_checkpoint_annotation_store import (
    ResearchCheckpointAnnotationStore,
)

from .in_memory_research_checkpoint_annotation_store import (
    InMemoryResearchCheckpointAnnotationStore,
)

from .json_research_checkpoint_annotation_store import (
    JsonResearchCheckpointAnnotationStore,
)

from .research_checkpoint_annotation_manager import (
    ResearchCheckpointAnnotationManager,
)

from .annotated_research_checkpoint import (
    AnnotatedResearchCheckpoint,
)

from .research_history_sort_order import (
    ResearchHistorySortOrder,
)

from .research_history_query import (
    ResearchHistoryQuery,
)

from .research_history_timeline_item import (
    ResearchHistoryTimelineItem,
)

from .research_history_page import (
    ResearchHistoryPage,
)

from .research_history_query_service import (
    ResearchHistoryQueryService,
)

from .research_session_branch import (
    ResearchSessionBranch,
)

from .research_session_branch_store import (
    ResearchSessionBranchStore,
)

from .in_memory_research_session_branch_store import (
    InMemoryResearchSessionBranchStore,
)

from .json_research_session_branch_store import (
    JsonResearchSessionBranchStore,
)

from .research_session_branch_manager import (
    ResearchSessionBranchManager,
)

from .research_session_lineage_node import (
    ResearchSessionLineageNode,
)

from .research_session_lineage_path import (
    ResearchSessionLineagePath,
)

from .research_session_lineage_service import (
    ResearchSessionLineageService,
)

from .research_session_lineage_summary import (
    ResearchSessionLineageSummary,
)

from .research_session_status import (
    ResearchSessionStatus,
)

from .research_session_profile import (
    ResearchSessionProfile,
)

from .research_session_profile_store import (
    ResearchSessionProfileStore,
)

from .in_memory_research_session_profile_store import (
    InMemoryResearchSessionProfileStore,
)

from .json_research_session_profile_store import (
    JsonResearchSessionProfileStore,
)

from .research_session_profile_manager import (
    ResearchSessionProfileManager,
)

from .research_session_kind import (
    ResearchSessionKind,
)

from .research_session_list_item import (
    ResearchSessionListItem,
)

from .research_session_page import (
    ResearchSessionPage,
)

from .research_session_query import (
    ResearchSessionQuery,
)

from .research_session_query_service import (
    ResearchSessionQueryService,
)

from .research_session_sort_order import (
    ResearchSessionSortOrder,
)

from .research_session_relationship import (
    ResearchSessionRelationship,
)

from .research_session_state_difference import (
    ResearchSessionStateDifference,
)

from .research_session_collection_difference import (
    ResearchSessionCollectionDifference,
)

from .research_session_divergence import (
    ResearchSessionDivergence,
)

from .research_session_lineage_comparison import (
    ResearchSessionLineageComparison,
)

from .research_session_lineage_comparison_service import (
    ResearchSessionLineageComparisonService,
)

from .research_tag_normalizer import (
    normalize_research_tag_name,
)

from .research_tag import (
    ResearchTag,
)

from .research_session_tag_assignment import (
    ResearchSessionTagAssignment,
)

from .research_tag_store import (
    ResearchTagStore,
)

from .in_memory_research_tag_store import (
    InMemoryResearchTagStore,
)

from .json_research_tag_store import (
    JsonResearchTagStore,
)

from .research_collection import (
    ResearchCollection,
)

from .research_collection_membership import (
    ResearchCollectionMembership,
)

from .research_collection_store import (
    ResearchCollectionStore,
)

from .in_memory_research_collection_store import (
    InMemoryResearchCollectionStore,
)

from .json_research_collection_store import (
    JsonResearchCollectionStore,
)

from .research_workspace_organization_service import (
    ResearchWorkspaceOrganizationService,
)

from .research_activity_type import (
    ResearchActivityType,
)

from .research_activity_actor_type import (
    ResearchActivityActorType,
)

from .research_activity_event import (
    ResearchActivityEvent,
)

from .research_activity_store import (
    ResearchActivityStore,
)

from .in_memory_research_activity_store import (
    InMemoryResearchActivityStore,
)

from .json_research_activity_store import (
    JsonResearchActivityStore,
)

from .research_activity_recorder import (
    ResearchActivityRecorder,
)

from .research_activity_query import (
    ResearchActivityQuery,
)

from .research_activity_page import (
    ResearchActivityPage,
)

from .research_activity_service import (
    ResearchActivityService,
)

from .research_workspace_overview import (
    ResearchWorkspaceOverview,
)

from .research_lifecycle_statistics import (
    ResearchLifecycleStatistics,
)

from .research_lineage_statistics import (
    ResearchLineageStatistics,
)

from .research_tag_statistic import (
    ResearchTagStatistic,
)

from .research_collection_statistic import (
    ResearchCollectionStatistic,
)

from .research_activity_statistics import (
    ResearchActivityStatistics,
)

from .research_session_activity_summary import (
    ResearchSessionActivitySummary,
)

from .research_workspace_insights import (
    ResearchWorkspaceInsights,
)

from .research_workspace_insights_service import (
    ResearchWorkspaceInsightsService,
)

from .research_snapshot_scope import (
    ResearchSnapshotScope,
)

from .research_snapshot_manifest import (
    ResearchSnapshotManifest,
)

from .research_snapshot import (
    ResearchSnapshot,
)

from .research_snapshot_validation_issue import (
    ResearchSnapshotValidationIssue,
)

from .research_snapshot_validation_result import (
    ResearchSnapshotValidationResult,
)

from .research_snapshot_validator import (
    ResearchSnapshotValidator,
)

from .research_snapshot_service import (
    ResearchSnapshotService,
)

from .research_snapshot_serializer import (
    ResearchSnapshotSerializer,
)

session_manager = SessionManager()
