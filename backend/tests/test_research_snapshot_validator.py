from datetime import (
    datetime,
    timezone,
)

from backend.session import (
    ResearchSnapshot,
    ResearchSnapshotManifest,
    ResearchSnapshotScope,
    ResearchSnapshotValidator,
)


def create_test_snapshot():

    return ResearchSnapshot(

        manifest=(

            ResearchSnapshotManifest(

                format_name=(
                    "prereqai.research_snapshot"
                ),

                schema_version=(
                    "1.0"
                ),

                snapshot_id=(
                    "snapshot-1"
                ),

                created_at=(

                    datetime(

                        2026,
                        7,
                        13,
                        12,
                        0,

                        tzinfo=(
                            timezone.utc
                        ),
                    )
                ),

                scope=(

                    ResearchSnapshotScope
                    .SESSION
                ),

                root_session_id=(
                    "session-a"
                ),
            )
        ),

        sessions=[

            {
                "session_id":
                    "session-a",
            },
        ],
    )


def test_valid_snapshot_has_no_issues():

    snapshot = (
        create_test_snapshot()
    )

    result = (

        ResearchSnapshotValidator()
        .validate(
            snapshot
        )
    )

    assert result.is_valid is True

    assert result.issues == []


def test_validator_detects_unsupported_schema_version():

    snapshot = (
        create_test_snapshot()
    )

    snapshot.manifest.schema_version = (
        "9.9"
    )

    result = (

        ResearchSnapshotValidator()
        .validate(
            snapshot
        )
    )

    assert result.is_valid is False

    assert any(

        issue.code

        == (
            "unsupported_schema_version"
        )

        for issue

        in result.issues
    )


def test_validator_detects_duplicate_session_ids():

    snapshot = (
        create_test_snapshot()
    )

    snapshot.sessions.append(

        {
            "session_id":
                "session-a",
        }
    )

    result = (

        ResearchSnapshotValidator()
        .validate(
            snapshot
        )
    )

    assert result.is_valid is False

    assert any(

        issue.code

        == "duplicate_session_id"

        for issue

        in result.issues
    )


def test_validator_detects_missing_branch_parent():

    snapshot = (
        create_test_snapshot()
    )

    snapshot.branches.append({

        "source_session_id":
            "missing-parent",

        "branch_session_id":
            "session-a",
    })

    validator = (
        ResearchSnapshotValidator()
    )

    result = (

        validator.validate(
            snapshot
        )
    )

    assert result.is_valid is False

    assert any(

        issue.code

        == "branch_parent_missing"

        for issue

        in result.issues
    )


def test_validator_detects_missing_tag_reference():

    snapshot = (
        create_test_snapshot()
    )

    snapshot.tag_assignments.append({

        "session_id":
            "session-a",

        "tag_id":
            "missing-tag",
    })

    result = (

        ResearchSnapshotValidator()
        .validate(
            snapshot
        )
    )

    assert result.is_valid is False

    assert any(

        issue.code

        == (
            "tag_assignment_tag_missing"
        )

        for issue

        in result.issues
    )


def test_validator_detects_missing_collection_reference():

    snapshot = (
        create_test_snapshot()
    )

    snapshot.collection_memberships.append({

        "session_id":
            "session-a",

        "collection_id":
            "missing-collection",
    })

    result = (

        ResearchSnapshotValidator()
        .validate(
            snapshot
        )
    )

    assert result.is_valid is False

    assert any(

        issue.code

        == (
            "collection_membership_collection_missing"
        )

        for issue

        in result.issues
    )


def test_validator_detects_external_activity_reference():

    snapshot = (
        create_test_snapshot()
    )

    snapshot.activity_events.append({

        "session_id":
            "session-a",

        "related_session_id":
            "session-outside",
    })

    result = (

        ResearchSnapshotValidator()
        .validate(
            snapshot
        )
    )

    assert result.is_valid is False

    assert any(

        issue.code

        == "activity_session_missing"

        for issue

        in result.issues
    )
