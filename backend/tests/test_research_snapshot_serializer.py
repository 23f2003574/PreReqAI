from datetime import (
    datetime,
    timezone,
)

from backend.session import (
    ResearchSnapshot,
    ResearchSnapshotManifest,
    ResearchSnapshotScope,
    ResearchSnapshotSerializer,
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

        profiles=[

            {

                "session_id":
                    "session-a",

                "display_name":
                    "Session A",
            },
        ],
    )


def test_snapshot_json_round_trip():

    snapshot = (
        create_test_snapshot()
    )

    serializer = (
        ResearchSnapshotSerializer()
    )

    payload = (

        serializer.dumps(
            snapshot
        )
    )

    restored = (

        serializer.loads(
            payload
        )
    )

    assert (

        restored.to_dict()

        == snapshot.to_dict()
    )


def test_snapshot_write_and_read_file(

    tmp_path,

):

    snapshot = (
        create_test_snapshot()
    )

    serializer = (
        ResearchSnapshotSerializer()
    )

    path = (

        tmp_path

        / "snapshot.json"
    )

    serializer.write(

        snapshot,

        path,
    )

    restored = (

        serializer.read(
            path
        )
    )

    assert (

        restored.to_dict()

        == snapshot.to_dict()
    )
