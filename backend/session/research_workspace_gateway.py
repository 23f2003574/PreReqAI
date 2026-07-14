from .research_snapshot_import_strategy import (
    ResearchSnapshotImportStrategy,
)

from .research_workspace_consumer_projection_execution_result import (
    ResearchWorkspaceConsumerProjectionExecutionResult,
)


class ResearchWorkspaceGateway:
    """
    Stable application-facing facade over
    the complete research workspace system.

    The gateway coordinates access to
    high-level capabilities without exposing
    internal service topology.
    """

    def __init__(

        self,

        application,

        capabilities,

        readiness_assessor,

        bootstrap_projector,

        attention_projector,

        action_projector,

        context_factory,

        consumer_contract_registry,

        consumer_contract_manifest_provider,

        diagnostics_factory,

        execution_policy_registry,

        execution_budget_factory,

    ):

        self.application = (
            application
        )

        self.capabilities = (
            capabilities
        )

        self.readiness_assessor = (
            readiness_assessor
        )

        self.bootstrap_projector = (
            bootstrap_projector
        )

        self.attention_projector = (
            attention_projector
        )

        self.action_projector = (
            action_projector
        )

        self.context_factory = (
            context_factory
        )

        self.consumer_contract_registry = (
            consumer_contract_registry
        )

        self.consumer_contract_manifest_provider = (
            consumer_contract_manifest_provider
        )

        self.diagnostics_factory = (
            diagnostics_factory
        )

        self.execution_policy_registry = (
            execution_policy_registry
        )

        self.execution_budget_factory = (
            execution_budget_factory
        )

    def _create_budget(

        self,

        operation_name,

    ):

        policy = (

            self.execution_policy_registry
            .get_policy(
                operation_name
            )
        )

        if policy is None:

            return None

        return (

            self.execution_budget_factory
            .create(
                policy=policy,
            )
        )

    def diagnose_bootstrap(

        self,

        *,

        recent_session_limit=5,

        recent_activity_limit=10,

    ):

        collector = (

            self.diagnostics_factory
            .create(
                operation_name=(
                    "workspace.bootstrap"
                ),
            )
        )

        context = (

            self.context_factory
            .create(
                diagnostics=collector,
            )
        )

        budget = (

            self._create_budget(
                "workspace.bootstrap"
            )
        )

        projection = (

            self.bootstrap_projector
            .project(

                context=context,

                diagnostics=collector,

                budget=budget,

                recent_session_limit=(
                    recent_session_limit
                ),

                recent_activity_limit=(
                    recent_activity_limit
                ),
            )
        )

        return (

            ResearchWorkspaceConsumerProjectionExecutionResult(

                projection=projection,

                diagnostics=(
                    collector.finalize()
                ),
            )
        )

    def diagnose_attention(

        self,

        *,

        category=None,

        minimum_severity=None,

        actionable_only=False,

        limit=None,

    ):

        collector = (

            self.diagnostics_factory
            .create(
                operation_name=(
                    "workspace.attention"
                ),
            )
        )

        context = (

            self.context_factory
            .create(
                diagnostics=collector,
            )
        )

        projection = (

            self.attention_projector
            .project(

                context=context,

                diagnostics=collector,

                category=category,

                minimum_severity=(
                    minimum_severity
                ),

                actionable_only=(
                    actionable_only
                ),

                limit=limit,
            )
        )

        return (

            ResearchWorkspaceConsumerProjectionExecutionResult(

                projection=projection,

                diagnostics=(
                    collector.finalize()
                ),
            )
        )

    def diagnose_workspace_actions(

        self,

        *,

        include_unavailable=False,

    ):

        collector = (

            self.diagnostics_factory
            .create(
                operation_name=(
                    "workspace.actions"
                ),
            )
        )

        context = (

            self.context_factory
            .create(
                diagnostics=collector,
            )
        )

        projection = (

            self.action_projector
            .project_workspace_actions(

                context=context,

                diagnostics=collector,

                include_unavailable=(
                    include_unavailable
                ),
            )
        )

        return (

            ResearchWorkspaceConsumerProjectionExecutionResult(

                projection=projection,

                diagnostics=(
                    collector.finalize()
                ),
            )
        )

    def diagnose_session_actions(

        self,

        session_id,

        *,

        include_unavailable=False,

    ):

        collector = (

            self.diagnostics_factory
            .create(
                operation_name=(
                    "session.actions"
                ),
            )
        )

        context = (

            self.context_factory
            .create(
                diagnostics=collector,
            )
        )

        projection = (

            self.action_projector
            .project_session_actions(

                session_id,

                context=context,

                diagnostics=collector,

                include_unavailable=(
                    include_unavailable
                ),
            )
        )

        return (

            ResearchWorkspaceConsumerProjectionExecutionResult(

                projection=projection,

                diagnostics=(
                    collector.finalize()
                ),
            )
        )

    def get_consumer_contract_manifest(

        self,

        *,

        scope=None,

        stability=None,

    ):

        return (

            self
            .consumer_contract_manifest_provider
            .get_manifest(

                scope=scope,

                stability=stability,
            )
        )

    def get_consumer_contract(

        self,

        contract_id,

    ):

        return (

            self
            .consumer_contract_registry
            .get_contract(
                contract_id
            )
        )

    def check_consumer_contract_compatibility(

        self,

        contract_id,

        requested_version,

    ):

        return (

            self
            .consumer_contract_registry
            .check_compatibility(

                contract_id,

                requested_version,
            )
        )

    def assess_readiness(self):

        return (

            self.readiness_assessor
            .assess()
        )

    def get_bootstrap(

        self,

        recent_session_limit=5,

        recent_activity_limit=10,

    ):

        context = (

            self.context_factory
            .create()
        )

        budget = (

            self._create_budget(
                "workspace.bootstrap"
            )
        )

        return (

            self.bootstrap_projector
            .project(

                context=context,

                budget=budget,

                recent_session_limit=(
                    recent_session_limit
                ),

                recent_activity_limit=(
                    recent_activity_limit
                ),
            )
        )

    def get_attention(

        self,

        *,

        category=None,

        minimum_severity=None,

        actionable_only=False,

        limit=None,

    ):

        context = (

            self.context_factory
            .create()
        )

        return (

            self.attention_projector
            .project(

                context=context,

                category=category,

                minimum_severity=(
                    minimum_severity
                ),

                actionable_only=(
                    actionable_only
                ),

                limit=limit,
            )
        )

    def list_workspace_actions(

        self,

        *,

        include_unavailable=False,

    ):

        context = (

            self.context_factory
            .create()
        )

        return (

            self.action_projector
            .project_workspace_actions(

                context=context,

                include_unavailable=(
                    include_unavailable
                ),
            )
        )

    def list_session_actions(

        self,

        session_id,

        *,

        include_unavailable=False,

    ):

        context = (

            self.context_factory
            .create()
        )

        return (

            self.action_projector
            .project_session_actions(

                session_id,

                context=context,

                include_unavailable=(
                    include_unavailable
                ),
            )
        )

    def list_capabilities(self):

        return (

            self.capabilities
            .list_capabilities()
        )

    def get_capability(

        self,

        name,

    ):

        return (

            self.capabilities
            .get_capability(
                name
            )
        )

    def supports(

        self,

        capability,

    ):

        return (

            self.capabilities
            .supports(
                capability
            )
        )

    def describe(self):

        return {

            "name":
                "PreReqAI Research Workspace",

            "capability_count":
                len(
                    self.list_capabilities()
                ),

            "capabilities": [

                capability.to_dict()

                for capability

                in self.list_capabilities()
            ],

            "latest_change_sequence":
                self.get_latest_change_sequence(),
        }

    def create_session(

        self,

        session_id,

        *,

        paper_id=None,

        paper_title=None,

    ):

        self.application.activate_research_session(

            session_id,

            paper_id=paper_id,

            paper_title=paper_title,
        )

        return (

            self.application
            .save_research_session(

                session_id,

                paper_id=paper_id,

                paper_title=paper_title,
            )
        )

    def get_session(

        self,

        session_id,

    ):

        return (

            self.application
            .get_research_session(

                session_id
            )
        )

    def get_session_profile(

        self,

        session_id,

    ):

        return (

            self.application
            .research_session_profile(

                session_id
            )
        )

    def update_session_profile(

        self,

        session_id,

        **changes,

    ):

        return (

            self.application
            .update_research_session_profile(

                session_id,

                **changes,
            )
        )

    def update_lifecycle_state(

        self,

        session_id,

        status,

    ):

        return (

            self.application
            .update_research_session_profile(

                session_id,

                status=status,
            )
        )

    def create_checkpoint(

        self,

        session_id,

        **options,

    ):

        if (

            self.application
            .active_session_id

            != session_id
        ):

            self.application.activate_research_session(
                session_id
            )

        return (

            self.application
            .checkpoint_research_session()
        )

    def search_sessions(

        self,

        **query,

    ):

        return (

            self.application
            .query_research_sessions(

                **query
            )
        )

    def branch_session(

        self,

        session_id,

        branch_session_id=None,

        display_name=None,

        description=None,

        metadata=None,

    ):

        checkpoint = (

            self.application
            .latest_research_checkpoint(

                session_id
            )
        )

        if checkpoint is None:

            checkpoint = (

                self.create_checkpoint(
                    session_id
                )
            )

        return (

            self.application
            .branch_research_checkpoint(

                checkpoint.id,

                branch_session_id=(
                    branch_session_id
                ),

                display_name=(
                    display_name
                ),

                description=(
                    description
                ),

                metadata=metadata,
            )
        )

    def get_lineage(

        self,

        session_id,

    ):

        return (

            self.application
            .research_session_lineage_tree(

                session_id
            )
        )

    def get_ancestors(

        self,

        session_id,

    ):

        return (

            self.application
            .research_session_ancestors(

                session_id
            )
        )

    def get_descendants(

        self,

        session_id,

    ):

        return (

            self.application
            .research_session_descendants(

                session_id
            )
        )

    def compare_sessions(

        self,

        first_session_id,

        second_session_id,

    ):

        return (

            self.application
            .compare_research_sessions(

                first_session_id,

                second_session_id,
            )
        )

    def create_tag(

        self,

        name,

    ):

        return (

            self.application
            .workspace_organization_service
            .get_or_create_tag(

                name
            )
        )

    def assign_tag(

        self,

        session_id,

        tag_name,

    ):

        return (

            self.application
            .tag_research_session(

                session_id,

                tag_name,
            )
        )

    def remove_tag_assignment(

        self,

        session_id,

        tag_name,

    ):

        return (

            self.application
            .untag_research_session(

                session_id,

                tag_name,
            )
        )

    def create_collection(

        self,

        name,

        description=None,

    ):

        return (

            self.application
            .create_research_collection(

                name,

                description,
            )
        )

    def add_collection_member(

        self,

        collection_id,

        session_id,

    ):

        return (

            self.application
            .add_research_session_to_collection(

                collection_id,

                session_id,
            )
        )

    def remove_collection_member(

        self,

        collection_id,

        session_id,

    ):

        return (

            self.application
            .remove_research_session_from_collection(

                collection_id,

                session_id,
            )
        )

    def get_activity(

        self,

        session_id=None,

        page=1,

        page_size=50,

    ):

        if session_id is not None:

            return (

                self.application
                .research_session_activity(

                    session_id,

                    page=page,

                    page_size=page_size,
                )
            )

        return (

            self.application
            .recent_research_activity(

                page=page,

                page_size=page_size,
            )
        )

    def get_workspace_insights(

        self,

        **options,

    ):

        return (

            self.application
            .research_workspace_insights(

                **options
            )
        )

    def export_workspace(self):

        return (

            self.application
            .export_research_workspace()
        )

    def serialize_snapshot(

        self,

        snapshot=None,

    ):

        if snapshot is None:

            snapshot = (
                self.export_workspace()
            )

        return (

            self.application
            .serialize_research_snapshot(

                snapshot
            )
        )

    def preview_import(

        self,

        snapshot,

        strategy=(

            ResearchSnapshotImportStrategy
            .REJECT
        ),

    ):

        return (

            self.application
            .preview_research_snapshot_import(

                snapshot,

                strategy=strategy,
            )
        )

    def import_snapshot(

        self,

        snapshot,

        strategy=(

            ResearchSnapshotImportStrategy
            .REJECT
        ),

    ):

        return (

            self.application
            .import_research_snapshot(

                snapshot,

                strategy=strategy,
            )
        )

    def audit_workspace(self):

        return (

            self.application
            .audit_research_workspace()
        )

    def plan_repairs(

        self,

        report=None,

    ):

        return (

            self.application
            .plan_research_workspace_repairs(

                report
            )
        )

    def get_changes(

        self,

        after_sequence=0,

        limit=100,

        entity_types=None,

        operations=None,

    ):

        return (

            self.application
            .get_research_workspace_changes(

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

    def get_latest_change_sequence(self):

        return (

            self.application
            .get_latest_research_workspace_change_sequence()
        )

    def subscribe(

        self,

        callback,

        entity_types=None,

        operations=None,

    ):

        return (

            self.application
            .subscribe_to_research_workspace_changes(

                callback=callback,

                entity_types=(
                    entity_types
                ),

                operations=(
                    operations
                ),
            )
        )

    def unsubscribe(

        self,

        subscription_id,

    ):

        return (

            self.application
            .unsubscribe_from_research_workspace_changes(

                subscription_id
            )
        )
