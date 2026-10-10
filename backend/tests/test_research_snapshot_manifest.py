from datetime import (
    datetime,
    timezone,
)

from backend.session import (
    ResearchSnapshotManifest,
    ResearchSnapshotScope,
)


def test_snapshot_manifest_round_trip():

    manifest = (

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
                .LINEAGE
            ),

            root_session_id=(
                "session-root"
            ),
        )
    )

    restored = (

        ResearchSnapshotManifest
        .from_dict(

            manifest.to_dict()
        )
    )

    assert restored == manifest
