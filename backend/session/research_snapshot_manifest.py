from dataclasses import (
    dataclass,
)

from datetime import (
    datetime,
)

from .research_snapshot_scope import (
    ResearchSnapshotScope,
)


@dataclass
class ResearchSnapshotManifest:
    """
    Describes the identity, schema version,
    scope, and creation metadata of a
    portable research snapshot.
    """

    format_name: str

    schema_version: str

    snapshot_id: str

    created_at: datetime

    scope: (
        ResearchSnapshotScope
    )

    root_session_id: (
        str | None
    )

    application_name: str = (
        "PreReqAI"
    )

    def to_dict(self):

        return {

            "format_name":
                self.format_name,

            "schema_version":
                self.schema_version,

            "snapshot_id":
                self.snapshot_id,

            "created_at":
                self.created_at
                .isoformat(),

            "scope":
                self.scope.value,

            "root_session_id":
                self.root_session_id,

            "application_name":
                self.application_name,
        }

    @classmethod
    def from_dict(

        cls,

        data,

    ):

        return cls(

            format_name=(
                data[
                    "format_name"
                ]
            ),

            schema_version=(
                data[
                    "schema_version"
                ]
            ),

            snapshot_id=(
                data[
                    "snapshot_id"
                ]
            ),

            created_at=(

                datetime
                .fromisoformat(

                    data[
                        "created_at"
                    ]
                )
            ),

            scope=(

                ResearchSnapshotScope(

                    data[
                        "scope"
                    ]
                )
            ),

            root_session_id=(

                data.get(
                    "root_session_id"
                )
            ),

            application_name=(

                data.get(

                    "application_name",

                    "PreReqAI",
                )
            ),
        )
