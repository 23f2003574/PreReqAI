from backend.session import (

    ResearchSessionSnapshot,

    ResearchSessionVersion,
)


def test_session_version_round_trip():

    snapshot = ResearchSessionSnapshot(

        session_id="session-1",

        paper_title="Example Paper",
    )

    version = ResearchSessionVersion(

        session_id="session-1",

        snapshot=snapshot,

        metadata={

            "reason":
                "workflow_progress",
        },
    )

    restored = (

        ResearchSessionVersion
        .from_dict(

            version.to_dict()
        )
    )

    assert restored.id == version.id

    assert (

        restored.session_id

        == "session-1"
    )

    assert (

        restored.snapshot
        .paper_title

        == "Example Paper"
    )
