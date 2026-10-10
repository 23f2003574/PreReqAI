from copy import (
    deepcopy,
)

from uuid import (
    uuid4,
)

from .research_snapshot_identity_map import (
    ResearchSnapshotIdentityMap,
)

from .research_snapshot_import_conflict import (
    ResearchSnapshotImportConflict,
)

from .research_snapshot_import_plan import (
    ResearchSnapshotImportPlan,
)

from .research_snapshot_import_strategy import (
    ResearchSnapshotImportStrategy,
)


class ResearchSnapshotImportPlanner:
    """
    Validates, analyzes, remaps, and rewrites
    a snapshot into a mutation-free import plan.
    """

    def __init__(

        self,

        session_manager,

        checkpoint_store,

        version_store,

        branch_store,

        tag_store,

        collection_store,

        activity_store,

        snapshot_validator,

        id_factory=None,

    ):

        self.session_manager = (
            session_manager
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

        self.snapshot_validator = (
            snapshot_validator
        )

        self.id_factory = (
            id_factory
        )

    def _new_id(self):

        if self.id_factory is not None:

            return self.id_factory()

        return str(
            uuid4()
        )

    def _existing_session_ids(self):

        return {

            session.session_id

            for session

            in self.session_manager
            .list_sessions()
        }

    def _existing_checkpoint_ids(

        self,

        existing_session_ids,

    ):

        return {

            checkpoint.id

            for session_id

            in existing_session_ids

            for checkpoint

            in self.checkpoint_store
            .list_for_session(

                session_id
            )
        }

    def _existing_version_ids(

        self,

        existing_session_ids,

    ):

        return {

            version.id

            for session_id

            in existing_session_ids

            for version

            in self.version_store
            .list_for_session(

                session_id
            )
        }

    def _existing_branch_ids(

        self,

        existing_session_ids,

    ):

        ids = set()

        for session_id in (

            existing_session_ids

        ):

            origin = (

                self.branch_store
                .get_by_branch_session(

                    session_id
                )
            )

            if origin is not None:

                ids.add(
                    origin.id
                )

        return ids

    def _existing_tag_ids(self):

        return {

            tag.id

            for tag

            in self.tag_store
            .list_tags()
        }

    def _existing_collection_ids(self):

        return {

            collection.id

            for collection

            in self.collection_store
            .list_collections()
        }

    def _existing_activity_event_ids(self):

        return {

            event.id

            for event

            in self.activity_store
            .list_all()
        }

    def _plan_identity_mapping(

        self,

        entity_type,

        imported_ids,

        existing_ids,

        strategy,

        mapping,

        conflicts,

    ):

        reserved_ids = set(
            existing_ids
        )

        for imported_id in sorted(

            imported_ids

        ):

            conflict = (

                imported_id

                in existing_ids
            )

            should_remap = (

                strategy

                == ResearchSnapshotImportStrategy
                .REMAP_ALL

                or

                (
                    strategy

                    == ResearchSnapshotImportStrategy
                    .REMAP_CONFLICTS

                    and conflict
                )
            )

            if (

                conflict

                and

                strategy

                == ResearchSnapshotImportStrategy
                .REJECT
            ):

                conflicts.append(

                    ResearchSnapshotImportConflict(

                        entity_type=(
                            entity_type
                        ),

                        imported_id=(
                            imported_id
                        ),

                        existing_id=(
                            imported_id
                        ),

                        resolution=(
                            "reject"
                        ),
                    )
                )

                mapping[
                    imported_id
                ] = imported_id

                continue

            if should_remap:

                new_id = None

                for _ in range(
                    100
                ):

                    candidate = (
                        self._new_id()
                    )

                    if (

                        candidate

                        not in reserved_ids
                    ):

                        new_id = (
                            candidate
                        )

                        break

                if new_id is None:

                    raise RuntimeError(

                        "Unable to generate "
                        "a unique import "
                        "identity."
                    )

                reserved_ids.add(
                    new_id
                )

                mapping[
                    imported_id
                ] = new_id

                if conflict:

                    conflicts.append(

                        ResearchSnapshotImportConflict(

                            entity_type=(
                                entity_type
                            ),

                            imported_id=(
                                imported_id
                            ),

                            existing_id=(
                                imported_id
                            ),

                            resolution=(
                                "remap"
                            ),

                            remapped_id=(
                                new_id
                            ),
                        )
                    )

            else:

                mapping[
                    imported_id
                ] = imported_id

                reserved_ids.add(
                    imported_id
                )

    def _build_identity_map(

        self,

        snapshot,

        strategy,

    ):

        identity_map = (

            ResearchSnapshotIdentityMap()
        )

        conflicts = []

        existing_session_ids = (

            self._existing_session_ids()
        )

        imported_session_ids = {

            record["session_id"]

            for record

            in snapshot.sessions
        }

        imported_checkpoint_ids = {

            record["id"]

            for record

            in snapshot.checkpoints
        }

        imported_version_ids = {

            record["id"]

            for record

            in snapshot.versions
        }

        imported_branch_ids = {

            record["id"]

            for record

            in snapshot.branches
        }

        imported_tag_ids = {

            record["id"]

            for record

            in snapshot.tags
        }

        imported_collection_ids = {

            record["id"]

            for record

            in snapshot.collections
        }

        imported_activity_event_ids = {

            record["id"]

            for record

            in snapshot.activity_events
        }

        self._plan_identity_mapping(

            entity_type="session",

            imported_ids=(
                imported_session_ids
            ),

            existing_ids=(
                existing_session_ids
            ),

            strategy=strategy,

            mapping=(
                identity_map.sessions
            ),

            conflicts=conflicts,
        )

        self._plan_identity_mapping(

            entity_type="checkpoint",

            imported_ids=(
                imported_checkpoint_ids
            ),

            existing_ids=(

                self._existing_checkpoint_ids(

                    existing_session_ids
                )
            ),

            strategy=strategy,

            mapping=(
                identity_map.checkpoints
            ),

            conflicts=conflicts,
        )

        self._plan_identity_mapping(

            entity_type="version",

            imported_ids=(
                imported_version_ids
            ),

            existing_ids=(

                self._existing_version_ids(

                    existing_session_ids
                )
            ),

            strategy=strategy,

            mapping=(
                identity_map.versions
            ),

            conflicts=conflicts,
        )

        self._plan_identity_mapping(

            entity_type="branch",

            imported_ids=(
                imported_branch_ids
            ),

            existing_ids=(

                self._existing_branch_ids(

                    existing_session_ids
                )
            ),

            strategy=strategy,

            mapping=(
                identity_map.branches
            ),

            conflicts=conflicts,
        )

        self._plan_identity_mapping(

            entity_type="tag",

            imported_ids=(
                imported_tag_ids
            ),

            existing_ids=(

                self._existing_tag_ids()
            ),

            strategy=strategy,

            mapping=(
                identity_map.tags
            ),

            conflicts=conflicts,
        )

        self._plan_identity_mapping(

            entity_type="collection",

            imported_ids=(
                imported_collection_ids
            ),

            existing_ids=(

                self
                ._existing_collection_ids()
            ),

            strategy=strategy,

            mapping=(
                identity_map.collections
            ),

            conflicts=conflicts,
        )

        self._plan_identity_mapping(

            entity_type="activity_event",

            imported_ids=(
                imported_activity_event_ids
            ),

            existing_ids=(

                self
                ._existing_activity_event_ids()
            ),

            strategy=strategy,

            mapping=(
                identity_map
                .activity_events
            ),

            conflicts=conflicts,
        )

        return (
            identity_map,
            conflicts,
        )

    def _rewrite_sessions(

        self,

        snapshot,

        identity_map,

    ):

        records = deepcopy(
            snapshot.sessions
        )

        for record in records:

            record["session_id"] = (

                identity_map
                .map_session(

                    record["session_id"]
                )
            )

        return records

    def _rewrite_profiles(

        self,

        snapshot,

        identity_map,

    ):

        records = deepcopy(
            snapshot.profiles
        )

        for record in records:

            record["session_id"] = (

                identity_map
                .map_session(

                    record["session_id"]
                )
            )

        return records

    def _rewrite_checkpoints(

        self,

        snapshot,

        identity_map,

    ):

        records = deepcopy(
            snapshot.checkpoints
        )

        for record in records:

            record["id"] = (

                identity_map
                .map_checkpoint(

                    record["id"]
                )
            )

            record["session_id"] = (

                identity_map
                .map_session(

                    record["session_id"]
                )
            )

            if (

                record.get(
                    "snapshot_version_id"
                )

                is not None
            ):

                record[
                    "snapshot_version_id"
                ] = (

                    identity_map
                    .map_version(

                        record[
                            "snapshot_version_id"
                        ]
                    )
                )

        return records

    def _rewrite_versions(

        self,

        snapshot,

        identity_map,

    ):

        records = deepcopy(
            snapshot.versions
        )

        for record in records:

            record["id"] = (

                identity_map
                .map_version(

                    record["id"]
                )
            )

            record["session_id"] = (

                identity_map
                .map_session(

                    record["session_id"]
                )
            )

            embedded_snapshot = (

                record.get(
                    "snapshot"
                )
            )

            if (

                isinstance(

                    embedded_snapshot,

                    dict,
                )

                and

                embedded_snapshot.get(
                    "session_id"
                )

                is not None
            ):

                embedded_snapshot[
                    "session_id"
                ] = (

                    identity_map
                    .map_session(

                        embedded_snapshot[
                            "session_id"
                        ]
                    )
                )

        return records

    def _rewrite_branches(

        self,

        snapshot,

        identity_map,

    ):

        records = deepcopy(
            snapshot.branches
        )

        for record in records:

            record["id"] = (

                identity_map
                .map_branch(

                    record["id"]
                )
            )

            record[
                "source_session_id"
            ] = (

                identity_map
                .map_session(

                    record[
                        "source_session_id"
                    ]
                )
            )

            record[
                "branch_session_id"
            ] = (

                identity_map
                .map_session(

                    record[
                        "branch_session_id"
                    ]
                )
            )

            record[
                "source_checkpoint_id"
            ] = (

                identity_map
                .map_checkpoint(

                    record[
                        "source_checkpoint_id"
                    ]
                )
            )

            record[
                "source_version_id"
            ] = (

                identity_map
                .map_version(

                    record[
                        "source_version_id"
                    ]
                )
            )

        return records

    def _rewrite_tags(

        self,

        snapshot,

        identity_map,

    ):

        records = deepcopy(
            snapshot.tags
        )

        for record in records:

            record["id"] = (

                identity_map
                .map_tag(

                    record["id"]
                )
            )

        return records

    def _rewrite_tag_assignments(

        self,

        snapshot,

        identity_map,

    ):

        records = deepcopy(
            snapshot.tag_assignments
        )

        for record in records:

            record["session_id"] = (

                identity_map
                .map_session(

                    record["session_id"]
                )
            )

            record["tag_id"] = (

                identity_map
                .map_tag(

                    record["tag_id"]
                )
            )

        return records

    def _rewrite_collections(

        self,

        snapshot,

        identity_map,

    ):

        records = deepcopy(
            snapshot.collections
        )

        for record in records:

            record["id"] = (

                identity_map
                .map_collection(

                    record["id"]
                )
            )

        return records

    def _rewrite_collection_memberships(

        self,

        snapshot,

        identity_map,

    ):

        records = deepcopy(

            snapshot
            .collection_memberships
        )

        for record in records:

            record["collection_id"] = (

                identity_map
                .map_collection(

                    record[
                        "collection_id"
                    ]
                )
            )

            record["session_id"] = (

                identity_map
                .map_session(

                    record["session_id"]
                )
            )

        return records

    def _rewrite_activity_events(

        self,

        snapshot,

        identity_map,

    ):

        records = deepcopy(
            snapshot.activity_events
        )

        for record in records:

            record["id"] = (

                identity_map
                .map_activity_event(

                    record["id"]
                )
            )

            if (

                record.get(
                    "session_id"
                )

                is not None
            ):

                record["session_id"] = (

                    identity_map
                    .map_session(

                        record[
                            "session_id"
                        ]
                    )
                )

            if (

                record.get(
                    "related_session_id"
                )

                is not None
            ):

                record[
                    "related_session_id"
                ] = (

                    identity_map
                    .map_session(

                        record[
                            "related_session_id"
                        ]
                    )
                )

        return records

    def plan_import(

        self,

        snapshot,

        strategy=(

            ResearchSnapshotImportStrategy
            .REJECT
        ),

    ):

        validation = (

            self.snapshot_validator
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

                "Cannot import invalid "
                "research snapshot: "
                f"{details}"
            )

        (
            identity_map,
            conflicts,

        ) = (

            self._build_identity_map(

                snapshot=snapshot,

                strategy=strategy,
            )
        )

        return (

            ResearchSnapshotImportPlan(

                snapshot_id=(

                    snapshot.manifest
                    .snapshot_id
                ),

                strategy=strategy,

                identity_map=(
                    identity_map
                ),

                conflicts=conflicts,

                sessions=(

                    self._rewrite_sessions(

                        snapshot,

                        identity_map,
                    )
                ),

                profiles=(

                    self._rewrite_profiles(

                        snapshot,

                        identity_map,
                    )
                ),

                checkpoints=(

                    self._rewrite_checkpoints(

                        snapshot,

                        identity_map,
                    )
                ),

                versions=(

                    self._rewrite_versions(

                        snapshot,

                        identity_map,
                    )
                ),

                branches=(

                    self._rewrite_branches(

                        snapshot,

                        identity_map,
                    )
                ),

                tags=(

                    self._rewrite_tags(

                        snapshot,

                        identity_map,
                    )
                ),

                tag_assignments=(

                    self._rewrite_tag_assignments(

                        snapshot,

                        identity_map,
                    )
                ),

                collections=(

                    self._rewrite_collections(

                        snapshot,

                        identity_map,
                    )
                ),

                collection_memberships=(

                    self
                    ._rewrite_collection_memberships(

                        snapshot,

                        identity_map,
                    )
                ),

                activity_events=(

                    self._rewrite_activity_events(

                        snapshot,

                        identity_map,
                    )
                ),
            )
        )
