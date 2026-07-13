from .research_activity_event import (
    ResearchActivityEvent,
)

from .research_collection import (
    ResearchCollection,
)

from .research_collection_membership import (
    ResearchCollectionMembership,
)

from .research_checkpoint import (
    ResearchCheckpoint,
)

from .research_session_branch import (
    ResearchSessionBranch,
)

from .research_session_profile import (
    ResearchSessionProfile,
)

from .research_session_snapshot import (
    ResearchSessionSnapshot,
)

from .research_session_tag_assignment import (
    ResearchSessionTagAssignment,
)

from .research_session_version import (
    ResearchSessionVersion,
)

from .research_snapshot_import_result import (
    ResearchSnapshotImportResult,
)

from .research_snapshot_import_strategy import (
    ResearchSnapshotImportStrategy,
)

from .research_tag import (
    ResearchTag,
)


class ResearchSnapshotImportService:
    """
    Applies validated import plans atomically
    to the research workspace.
    """

    def __init__(

        self,

        import_planner,

        transaction_factory,

        session_manager,

        profile_store,

        checkpoint_store,

        version_store,

        branch_store,

        tag_store,

        collection_store,

        activity_store,

    ):

        self.import_planner = (
            import_planner
        )

        self.transaction_factory = (
            transaction_factory
        )

        self.session_manager = (
            session_manager
        )

        self.profile_store = (
            profile_store
        )

        self.checkpoint_store = (
            checkpoint_store
        )

        self.version_store = (
            version_store
        )

        self.branch_store = (
            branch_store
        )

        self.tag_store = (
            tag_store
        )

        self.collection_store = (
            collection_store
        )

        self.activity_store = (
            activity_store
        )

    def preview(

        self,

        snapshot,

        strategy=(

            ResearchSnapshotImportStrategy
            .REJECT
        ),

    ):

        return (

            self.import_planner
            .plan_import(

                snapshot=snapshot,

                strategy=strategy,
            )
        )

    def _apply_sessions(

        self,

        records,

    ):

        for record in records:

            self.session_manager.restore_session_record(

                ResearchSessionSnapshot
                .from_dict(
                    record
                )
            )

    def _apply_profiles(

        self,

        records,

    ):

        for record in records:

            self.profile_store.save(

                ResearchSessionProfile
                .from_dict(
                    record
                )
            )

    def _apply_checkpoints(

        self,

        records,

    ):

        for record in records:

            self.checkpoint_store.save(

                ResearchCheckpoint
                .from_dict(
                    record
                )
            )

    def _apply_versions(

        self,

        records,

    ):

        for record in records:

            self.version_store.save(

                ResearchSessionVersion
                .from_dict(
                    record
                )
            )

    def _apply_branches(

        self,

        records,

    ):

        for record in records:

            self.branch_store.save(

                ResearchSessionBranch
                .from_dict(
                    record
                )
            )

    def _apply_tags(

        self,

        records,

    ):

        for record in records:

            self.tag_store.save_tag(

                ResearchTag.from_dict(
                    record
                )
            )

    def _apply_tag_assignments(

        self,

        records,

    ):

        for record in records:

            self.tag_store.assign(

                ResearchSessionTagAssignment
                .from_dict(
                    record
                )
            )

    def _apply_collections(

        self,

        records,

    ):

        for record in records:

            self.collection_store.save_collection(

                ResearchCollection
                .from_dict(
                    record
                )
            )

    def _apply_collection_memberships(

        self,

        records,

    ):

        for record in records:

            self.collection_store.add_membership(

                ResearchCollectionMembership
                .from_dict(
                    record
                )
            )

    def _apply_activity_events(

        self,

        records,

    ):

        for record in records:

            self.activity_store.append(

                ResearchActivityEvent
                .from_dict(
                    record
                )
            )

    def _apply_plan(

        self,

        plan,

    ):

        self._apply_sessions(
            plan.sessions
        )

        self._apply_profiles(
            plan.profiles
        )

        self._apply_checkpoints(
            plan.checkpoints
        )

        self._apply_versions(
            plan.versions
        )

        self._apply_branches(
            plan.branches
        )

        self._apply_tags(
            plan.tags
        )

        self._apply_tag_assignments(

            plan.tag_assignments
        )

        self._apply_collections(
            plan.collections
        )

        self._apply_collection_memberships(

            plan
            .collection_memberships
        )

        self._apply_activity_events(

            plan.activity_events
        )

    def import_snapshot(

        self,

        snapshot,

        strategy=(

            ResearchSnapshotImportStrategy
            .REJECT
        ),

    ):

        plan = (

            self.preview(

                snapshot=snapshot,

                strategy=strategy,
            )
        )

        if (

            strategy

            == ResearchSnapshotImportStrategy
            .REJECT

            and

            plan.has_conflicts
        ):

            raise ValueError(

                "Research snapshot import "
                "contains identity "
                "conflicts."
            )

        transaction = (

            self.transaction_factory()
        )

        with transaction:

            self._apply_plan(
                plan
            )

        return (

            ResearchSnapshotImportResult(

                snapshot_id=(
                    plan.snapshot_id
                ),

                identity_map=(
                    plan.identity_map
                ),

                imported_sessions=(
                    len(
                        plan.sessions
                    )
                ),

                imported_profiles=(
                    len(
                        plan.profiles
                    )
                ),

                imported_checkpoints=(
                    len(
                        plan.checkpoints
                    )
                ),

                imported_versions=(
                    len(
                        plan.versions
                    )
                ),

                imported_branches=(
                    len(
                        plan.branches
                    )
                ),

                imported_tags=(
                    len(
                        plan.tags
                    )
                ),

                imported_tag_assignments=(
                    len(

                        plan
                        .tag_assignments
                    )
                ),

                imported_collections=(
                    len(
                        plan.collections
                    )
                ),

                imported_collection_memberships=(

                    len(

                        plan
                        .collection_memberships
                    )
                ),

                imported_activity_events=(

                    len(

                        plan
                        .activity_events
                    )
                ),
            )
        )
