from .research_snapshot_validation_issue import (
    ResearchSnapshotValidationIssue,
)

from .research_snapshot_validation_result import (
    ResearchSnapshotValidationResult,
)


class ResearchSnapshotValidator:
    """
    Validates portable research snapshot
    structure and referential integrity.
    """

    SUPPORTED_FORMAT = (
        "prereqai.research_snapshot"
    )

    SUPPORTED_SCHEMA_VERSION = (
        "1.0"
    )

    def _validate_manifest(

        self,

        snapshot,

        issues,

    ):

        manifest = (
            snapshot.manifest
        )

        if (

            manifest.format_name

            != self.SUPPORTED_FORMAT
        ):

            issues.append(

                ResearchSnapshotValidationIssue(

                    code=(
                        "unsupported_format"
                    ),

                    message=(

                        "Unsupported snapshot "
                        "format: "
                        f"{manifest.format_name}"
                    ),

                    path=(
                        "manifest.format_name"
                    ),
                )
            )

        if (

            manifest.schema_version

            != (
                self
                .SUPPORTED_SCHEMA_VERSION
            )
        ):

            issues.append(

                ResearchSnapshotValidationIssue(

                    code=(
                        "unsupported_schema_version"
                    ),

                    message=(

                        "Unsupported snapshot "
                        "schema version: "
                        f"{manifest.schema_version}"
                    ),

                    path=(
                        "manifest.schema_version"
                    ),
                )
            )

    def _validate_duplicate_session_ids(

        self,

        snapshot,

        issues,

    ):

        seen = set()

        for index, session in enumerate(

            snapshot.sessions

        ):

            session_id = (

                session.get(
                    "session_id"
                )

                or

                session.get(
                    "id"
                )
            )

            if session_id is None:

                issues.append(

                    ResearchSnapshotValidationIssue(

                        code=(
                            "missing_session_id"
                        ),

                        message=(

                            "Snapshot session "
                            "record has no "
                            "identifier."
                        ),

                        path=(

                            f"sessions[{index}]"
                        ),
                    )
                )

                continue

            if session_id in seen:

                issues.append(

                    ResearchSnapshotValidationIssue(

                        code=(
                            "duplicate_session_id"
                        ),

                        message=(

                            "Duplicate session "
                            "identifier: "
                            f"{session_id}"
                        ),

                        path=(

                            f"sessions[{index}]"
                        ),
                    )
                )

            seen.add(
                session_id
            )

    def _validate_profiles(

        self,

        snapshot,

        session_ids,

        issues,

    ):

        for index, profile in enumerate(

            snapshot.profiles

        ):

            session_id = (

                profile.get(
                    "session_id"
                )
            )

            if session_id not in session_ids:

                issues.append(

                    ResearchSnapshotValidationIssue(

                        code=(
                            "profile_session_missing"
                        ),

                        message=(

                            "Profile references "
                            "a session not present "
                            "in the snapshot: "
                            f"{session_id}"
                        ),

                        path=(

                            f"profiles[{index}]"
                            ".session_id"
                        ),
                    )
                )

    def _validate_checkpoints(

        self,

        snapshot,

        session_ids,

        issues,

    ):

        for index, checkpoint in enumerate(

            snapshot.checkpoints

        ):

            session_id = (

                checkpoint.get(
                    "session_id"
                )
            )

            if session_id not in session_ids:

                issues.append(

                    ResearchSnapshotValidationIssue(

                        code=(
                            "checkpoint_session_missing"
                        ),

                        message=(

                            "Checkpoint references "
                            "a session not present "
                            "in the snapshot: "
                            f"{session_id}"
                        ),

                        path=(

                            f"checkpoints[{index}]"
                            ".session_id"
                        ),
                    )
                )

    def _validate_versions(

        self,

        snapshot,

        session_ids,

        issues,

    ):

        for index, version in enumerate(

            snapshot.versions

        ):

            session_id = (

                version.get(
                    "session_id"
                )
            )

            if session_id not in session_ids:

                issues.append(

                    ResearchSnapshotValidationIssue(

                        code=(
                            "version_session_missing"
                        ),

                        message=(

                            "Immutable version "
                            "references a session "
                            "not present in the "
                            "snapshot: "
                            f"{session_id}"
                        ),

                        path=(

                            f"versions[{index}]"
                            ".session_id"
                        ),
                    )
                )

    def _validate_branches(

        self,

        snapshot,

        session_ids,

        issues,

    ):

        for index, branch in enumerate(

            snapshot.branches

        ):

            source_session_id = (

                branch.get(
                    "source_session_id"
                )
            )

            branch_session_id = (

                branch.get(
                    "branch_session_id"
                )
            )

            if (

                source_session_id

                not in session_ids
            ):

                issues.append(

                    ResearchSnapshotValidationIssue(

                        code=(
                            "branch_parent_missing"
                        ),

                        message=(

                            "Branch references "
                            "a missing parent "
                            "session: "
                            f"{source_session_id}"
                        ),

                        path=(

                            f"branches[{index}]"
                            ".source_session_id"
                        ),
                    )
                )

            if (

                branch_session_id

                not in session_ids
            ):

                issues.append(

                    ResearchSnapshotValidationIssue(

                        code=(
                            "branch_session_missing"
                        ),

                        message=(

                            "Branch references "
                            "a missing child "
                            "session: "
                            f"{branch_session_id}"
                        ),

                        path=(

                            f"branches[{index}]"
                            ".branch_session_id"
                        ),
                    )
                )

    def _validate_tag_assignments(

        self,

        snapshot,

        session_ids,

        tag_ids,

        issues,

    ):

        for index, assignment in enumerate(

            snapshot.tag_assignments

        ):

            session_id = (

                assignment.get(
                    "session_id"
                )
            )

            tag_id = (

                assignment.get(
                    "tag_id"
                )
            )

            if session_id not in session_ids:

                issues.append(

                    ResearchSnapshotValidationIssue(

                        code=(
                            "tag_assignment_session_missing"
                        ),

                        message=(

                            "Tag assignment "
                            "references a missing "
                            "session: "
                            f"{session_id}"
                        ),

                        path=(

                            f"tag_assignments[{index}]"
                            ".session_id"
                        ),
                    )
                )

            if tag_id not in tag_ids:

                issues.append(

                    ResearchSnapshotValidationIssue(

                        code=(
                            "tag_assignment_tag_missing"
                        ),

                        message=(

                            "Tag assignment "
                            "references a missing "
                            "tag: "
                            f"{tag_id}"
                        ),

                        path=(

                            f"tag_assignments[{index}]"
                            ".tag_id"
                        ),
                    )
                )

    def _validate_collection_memberships(

        self,

        snapshot,

        session_ids,

        collection_ids,

        issues,

    ):

        for index, membership in enumerate(

            snapshot.collection_memberships

        ):

            session_id = (

                membership.get(
                    "session_id"
                )
            )

            collection_id = (

                membership.get(
                    "collection_id"
                )
            )

            if session_id not in session_ids:

                issues.append(

                    ResearchSnapshotValidationIssue(

                        code=(
                            "collection_membership_session_missing"
                        ),

                        message=(

                            "Collection membership "
                            "references a missing "
                            "session: "
                            f"{session_id}"
                        ),

                        path=(

                            "collection_memberships"
                            f"[{index}].session_id"
                        ),
                    )
                )

            if (

                collection_id

                not in collection_ids
            ):

                issues.append(

                    ResearchSnapshotValidationIssue(

                        code=(
                            "collection_membership_collection_missing"
                        ),

                        message=(

                            "Collection membership "
                            "references a missing "
                            "collection: "
                            f"{collection_id}"
                        ),

                        path=(

                            "collection_memberships"
                            f"[{index}].collection_id"
                        ),
                    )
                )

    def _validate_activity_events(

        self,

        snapshot,

        session_ids,

        issues,

    ):

        for index, event in enumerate(

            snapshot.activity_events

        ):

            for field_name in [

                "session_id",

                "related_session_id",
            ]:

                session_id = (

                    event.get(
                        field_name
                    )
                )

                if (

                    session_id is not None

                    and

                    session_id
                    not in session_ids
                ):

                    issues.append(

                        ResearchSnapshotValidationIssue(

                            code=(
                                "activity_session_missing"
                            ),

                            message=(

                                "Activity event "
                                "references a session "
                                "not present in the "
                                "snapshot: "
                                f"{session_id}"
                            ),

                            path=(

                                f"activity_events[{index}]"
                                f".{field_name}"
                            ),
                        )
                    )

    def validate(

        self,

        snapshot,

    ):

        issues = []

        self._validate_manifest(

            snapshot,

            issues,
        )

        self._validate_duplicate_session_ids(

            snapshot,

            issues,
        )

        session_ids = {

            (
                session.get(
                    "session_id"
                )

                or

                session.get(
                    "id"
                )
            )

            for session

            in snapshot.sessions
        }

        session_ids.discard(
            None
        )

        tag_ids = {

            tag.get(
                "id"
            )

            for tag

            in snapshot.tags
        }

        tag_ids.discard(
            None
        )

        collection_ids = {

            collection.get(
                "id"
            )

            for collection

            in snapshot.collections
        }

        collection_ids.discard(
            None
        )

        self._validate_profiles(

            snapshot,

            session_ids,

            issues,
        )

        self._validate_checkpoints(

            snapshot,

            session_ids,

            issues,
        )

        self._validate_versions(

            snapshot,

            session_ids,

            issues,
        )

        self._validate_branches(

            snapshot,

            session_ids,

            issues,
        )

        self._validate_tag_assignments(

            snapshot,

            session_ids,

            tag_ids,

            issues,
        )

        self._validate_collection_memberships(

            snapshot,

            session_ids,

            collection_ids,

            issues,
        )

        self._validate_activity_events(

            snapshot,

            session_ids,

            issues,
        )

        return (

            ResearchSnapshotValidationResult(

                issues=issues
            )
        )
