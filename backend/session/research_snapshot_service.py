from datetime import (
    datetime,
    timezone,
)

from uuid import (
    uuid4,
)

from .research_snapshot import (
    ResearchSnapshot,
)

from .research_snapshot_manifest import (
    ResearchSnapshotManifest,
)

from .research_snapshot_scope import (
    ResearchSnapshotScope,
)


class ResearchSnapshotService:
    """
    Builds portable research snapshots
    from canonical domain stores.
    """

    FORMAT_NAME = (
        "prereqai.research_snapshot"
    )

    SCHEMA_VERSION = (
        "1.0"
    )

    def __init__(

        self,

        session_manager,

        profile_store,

        checkpoint_store,

        version_store,

        branch_store,

        lineage_service,

        tag_store,

        collection_store,

        activity_store,

        validator,

        clock=None,

        id_factory=None,

    ):

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

        self.lineage_service = (
            lineage_service
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

        self.validator = (
            validator
        )

        self.clock = (
            clock
        )

        self.id_factory = (
            id_factory
        )

    def _now(self):

        if self.clock is not None:

            return self.clock()

        return datetime.now(
            timezone.utc
        )

    def _new_id(self):

        if self.id_factory is not None:

            return self.id_factory()

        return str(
            uuid4()
        )

    def _all_session_ids(self):

        return {

            session.session_id

            for session

            in self.session_manager
            .list_sessions()
        }

    def _resolve_single_session(

        self,

        session_id,

    ):

        session = (

            self.session_manager
            .load_session(

                session_id
            )
        )

        if session is None:

            raise ValueError(

                "Research session "
                "does not exist: "
                f"{session_id}"
            )

        return {
            session_id
        }

    def _resolve_session_with_descendants(

        self,

        session_id,

    ):

        self._resolve_single_session(

            session_id
        )

        descendants = (

            self.lineage_service
            .descendant_session_ids(

                session_id
            )
        )

        return {

            session_id,

            *descendants,
        }

    def _resolve_lineage(

        self,

        session_id,

    ):

        self._resolve_single_session(

            session_id
        )

        root_session_id = (

            self.lineage_service
            .root_session_id(

                session_id
            )
        )

        descendants = (

            self.lineage_service
            .descendant_session_ids(

                root_session_id
            )
        )

        return {

            root_session_id,

            *descendants,
        }

    def _resolve_session_ids(

        self,

        scope,

        root_session_id,

    ):

        if (

            scope

            == ResearchSnapshotScope
            .WORKSPACE
        ):

            return (
                self._all_session_ids()
            )

        if root_session_id is None:

            raise ValueError(

                "A root session ID "
                "is required for "
                f"snapshot scope {scope.value}"
            )

        if (

            scope

            == ResearchSnapshotScope
            .SESSION
        ):

            return (

                self._resolve_single_session(

                    root_session_id
                )
            )

        if (

            scope

            == ResearchSnapshotScope
            .SESSION_WITH_DESCENDANTS
        ):

            return (

                self
                ._resolve_session_with_descendants(

                    root_session_id
                )
            )

        if (

            scope

            == ResearchSnapshotScope
            .LINEAGE
        ):

            return (

                self._resolve_lineage(

                    root_session_id
                )
            )

        raise ValueError(

            "Unsupported research "
            "snapshot scope: "
            f"{scope}"
        )

    def _collect_sessions(

        self,

        session_ids,

    ):

        sessions = []

        for session_id in sorted(

            session_ids

        ):

            session = (

                self.session_manager
                .load_session(

                    session_id
                )
            )

            if session is None:

                continue

            sessions.append(

                session.to_dict()
            )

        return sessions

    def _collect_profiles(

        self,

        session_ids,

    ):

        profiles = []

        for session_id in sorted(

            session_ids

        ):

            profile = (

                self.profile_store
                .get(
                    session_id
                )
            )

            if profile is None:

                continue

            profiles.append(

                profile.to_dict()
            )

        return profiles

    def _collect_checkpoints(

        self,

        session_ids,

    ):

        checkpoints = []

        for session_id in sorted(

            session_ids

        ):

            for checkpoint in (

                self.checkpoint_store
                .list_for_session(

                    session_id
                )
            ):

                checkpoints.append(

                    checkpoint.to_dict()
                )

        checkpoints.sort(

            key=lambda item: (

                item.get(
                    "created_at",
                    "",
                ),

                item.get(
                    "id",
                    "",
                ),
            )
        )

        return checkpoints

    def _collect_versions(

        self,

        session_ids,

    ):

        versions = []

        for session_id in sorted(

            session_ids

        ):

            for version in (

                self.version_store
                .list_for_session(

                    session_id
                )
            ):

                versions.append(

                    version.to_dict()
                )

        versions.sort(

            key=lambda item: (

                item.get(
                    "created_at",
                    "",
                ),

                item.get(
                    "id",
                    "",
                ),
            )
        )

        return versions

    def _collect_branches(

        self,

        session_ids,

    ):

        branches = []

        for session_id in sorted(

            session_ids

        ):

            origin = (

                self.branch_store
                .get_by_branch_session(

                    session_id
                )
            )

            if origin is None:

                continue

            if (

                origin.source_session_id

                not in session_ids
            ):

                continue

            branches.append(

                origin.to_dict()
            )

        branches.sort(

            key=lambda item: (

                item.get(
                    "source_session_id",
                    "",
                ),

                item.get(
                    "branch_session_id",
                    "",
                ),
            )
        )

        return branches

    def _collect_tags_and_assignments(

        self,

        session_ids,

    ):

        assignments = []

        tag_ids = set()

        for session_id in sorted(

            session_ids

        ):

            for assignment in (

                self.tag_store
                .list_assignments_for_session(

                    session_id
                )
            ):

                assignments.append(

                    assignment.to_dict()
                )

                tag_ids.add(
                    assignment.tag_id
                )

        tags = []

        for tag_id in sorted(
            tag_ids
        ):

            tag = (

                self.tag_store
                .get_tag(
                    tag_id
                )
            )

            if tag is not None:

                tags.append(
                    tag.to_dict()
                )

        return (
            tags,
            assignments,
        )

    def _collect_collections_and_memberships(

        self,

        session_ids,

    ):

        memberships = []

        collection_ids = set()

        for session_id in sorted(

            session_ids

        ):

            for membership in (

                self.collection_store
                .list_memberships_for_session(

                    session_id
                )
            ):

                memberships.append(

                    membership.to_dict()
                )

                collection_ids.add(

                    membership
                    .collection_id
                )

        collections = []

        for collection_id in sorted(

            collection_ids

        ):

            collection = (

                self.collection_store
                .get_collection(

                    collection_id
                )
            )

            if collection is not None:

                collections.append(

                    collection.to_dict()
                )

        return (
            collections,
            memberships,
        )

    def _collect_activity_events(

        self,

        session_ids,

        scope,

    ):

        events = []

        for event in (

            self.activity_store
            .list_all()
        ):

            references = {

                event.session_id,

                event.related_session_id,
            }

            references.discard(
                None
            )

            if not references:

                if (

                    scope

                    == ResearchSnapshotScope
                    .WORKSPACE
                ):

                    events.append(

                        event.to_dict()
                    )

                continue

            if references.issubset(

                session_ids

            ):

                events.append(

                    event.to_dict()
                )

        events.sort(

            key=lambda item: (

                item.get(
                    "occurred_at",
                    "",
                ),

                item.get(
                    "id",
                    "",
                ),
            )
        )

        return events

    def build_snapshot(

        self,

        scope,

        root_session_id=None,

    ):

        session_ids = (

            self._resolve_session_ids(

                scope=scope,

                root_session_id=(
                    root_session_id
                ),
            )
        )

        tags, tag_assignments = (

            self._collect_tags_and_assignments(

                session_ids
            )
        )

        (
            collections,
            collection_memberships,

        ) = (

            self
            ._collect_collections_and_memberships(

                session_ids
            )
        )

        snapshot = (

            ResearchSnapshot(

                manifest=(

                    ResearchSnapshotManifest(

                        format_name=(
                            self.FORMAT_NAME
                        ),

                        schema_version=(
                            self.SCHEMA_VERSION
                        ),

                        snapshot_id=(
                            self._new_id()
                        ),

                        created_at=(
                            self._now()
                        ),

                        scope=scope,

                        root_session_id=(

                            root_session_id

                            if (

                                scope

                                != ResearchSnapshotScope
                                .WORKSPACE
                            )

                            else None
                        ),
                    )
                ),

                sessions=(

                    self._collect_sessions(

                        session_ids
                    )
                ),

                profiles=(

                    self._collect_profiles(

                        session_ids
                    )
                ),

                checkpoints=(

                    self._collect_checkpoints(

                        session_ids
                    )
                ),

                versions=(

                    self._collect_versions(

                        session_ids
                    )
                ),

                branches=(

                    self._collect_branches(

                        session_ids
                    )
                ),

                tags=tags,

                tag_assignments=(
                    tag_assignments
                ),

                collections=(
                    collections
                ),

                collection_memberships=(
                    collection_memberships
                ),

                activity_events=(

                    self._collect_activity_events(

                        session_ids=(
                            session_ids
                        ),

                        scope=scope,
                    )
                ),
            )
        )

        validation = (

            self.validator
            .validate(
                snapshot
            )
        )

        if not validation.is_valid:

            details = "; ".join(

                issue.message

                for issue

                in validation.issues
            )

            raise ValueError(

                "Generated research "
                "snapshot failed "
                f"validation: {details}"
            )

        return snapshot
