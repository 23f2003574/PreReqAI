from backend.session import (

    ResearchSessionComparator,

    ResearchSessionSnapshot,

    ResearchStateChangeType,
)


def test_detects_changed_session_field():

    comparator = (

        ResearchSessionComparator(

            fields=[
                "paper_title"
            ]
        )
    )

    current = ResearchSessionSnapshot(

        session_id="session-1",

        paper_title="Current Paper",
    )

    target = ResearchSessionSnapshot(

        session_id="session-1",

        paper_title="Historical Paper",
    )

    comparison = (

        comparator.compare(

            current,

            target,
        )
    )

    assert comparison.has_changes

    assert comparison.change_count == 1

    change = comparison.changes[0]

    assert (

        change.field

        == "paper_title"
    )

    assert (

        change.change_type

        == (
            ResearchStateChangeType
            .CHANGED
        )
    )

    assert (

        change.current_value

        == "Current Paper"
    )

    assert (

        change.target_value

        == "Historical Paper"
    )


def test_detects_added_target_value():

    comparator = (

        ResearchSessionComparator(

            fields=[
                "paper_title"
            ]
        )
    )

    current = ResearchSessionSnapshot(

        session_id="session-1",

        paper_title=None,
    )

    target = ResearchSessionSnapshot(

        session_id="session-1",

        paper_title="Historical Paper",
    )

    comparison = (

        comparator.compare(

            current,

            target,
        )
    )

    assert (

        comparison
        .changes[0]
        .change_type

        == (
            ResearchStateChangeType
            .ADDED
        )
    )


def test_detects_removed_target_value():

    comparator = (

        ResearchSessionComparator(

            fields=[
                "paper_title"
            ]
        )
    )

    current = ResearchSessionSnapshot(

        session_id="session-1",

        paper_title="Current Paper",
    )

    target = ResearchSessionSnapshot(

        session_id="session-1",

        paper_title=None,
    )

    comparison = (

        comparator.compare(

            current,

            target,
        )
    )

    assert (

        comparison
        .changes[0]
        .change_type

        == (
            ResearchStateChangeType
            .REMOVED
        )
    )


def test_reports_added_and_removed_collection_values():

    comparator = (

        ResearchSessionComparator(

            fields=[
                "artifact_ids"
            ]
        )
    )

    current = ResearchSessionSnapshot(

        session_id="session-1",

        artifact_ids=[

            "artifact-1",

            "artifact-2",
        ],
    )

    target = ResearchSessionSnapshot(

        session_id="session-1",

        artifact_ids=[

            "artifact-2",

            "artifact-3",
        ],
    )

    comparison = (

        comparator.compare(

            current,

            target,
        )
    )

    change = comparison.changes[0]

    assert (

        change.added_values

        == [
            "artifact-3"
        ]
    )

    assert (

        change.removed_values

        == [
            "artifact-1"
        ]
    )


def test_reports_no_changes_for_equal_snapshots():

    comparator = (

        ResearchSessionComparator(

            fields=[
                "paper_title"
            ]
        )
    )

    current = ResearchSessionSnapshot(

        session_id="session-1",

        paper_title="Same Paper",
    )

    target = ResearchSessionSnapshot(

        session_id="session-1",

        paper_title="Same Paper",
    )

    comparison = (

        comparator.compare(

            current,

            target,
        )
    )

    assert (

        comparison.has_changes

        is False
    )

    assert comparison.change_count == 0


def test_detects_changed_active_workflow_step():

    comparator = (

        ResearchSessionComparator(

            fields=[
                "active_workflow_step_id"
            ]
        )
    )

    current = ResearchSessionSnapshot(

        session_id="session-1",

        timeline=[

            {

                "id": "step-1",

                "title": "Explain",

                "status": "active",
            },
        ],
    )

    target = ResearchSessionSnapshot(

        session_id="session-1",

        timeline=[

            {

                "id": "step-2",

                "title": "Quiz",

                "status": "active",
            },
        ],
    )

    comparison = (

        comparator.compare(

            current,

            target,
        )
    )

    assert comparison.has_changes

    change = comparison.changes[0]

    assert (

        change.current_value

        == "step-1"
    )

    assert (

        change.target_value

        == "step-2"
    )
