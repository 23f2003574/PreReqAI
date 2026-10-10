from dataclasses import (
    dataclass,
    field,
)

from typing import (
    Any,
)

from .research_snapshot_manifest import (
    ResearchSnapshotManifest,
)


@dataclass
class ResearchSnapshot:
    """
    Portable representation of selected
    PreReqAI research domain state.
    """

    manifest: (
        ResearchSnapshotManifest
    )

    sessions: list[
        dict[
            str,
            Any,
        ]
    ] = field(
        default_factory=list,
    )

    profiles: list[
        dict[
            str,
            Any,
        ]
    ] = field(
        default_factory=list,
    )

    checkpoints: list[
        dict[
            str,
            Any,
        ]
    ] = field(
        default_factory=list,
    )

    versions: list[
        dict[
            str,
            Any,
        ]
    ] = field(
        default_factory=list,
    )

    branches: list[
        dict[
            str,
            Any,
        ]
    ] = field(
        default_factory=list,
    )

    tags: list[
        dict[
            str,
            Any,
        ]
    ] = field(
        default_factory=list,
    )

    tag_assignments: list[
        dict[
            str,
            Any,
        ]
    ] = field(
        default_factory=list,
    )

    collections: list[
        dict[
            str,
            Any,
        ]
    ] = field(
        default_factory=list,
    )

    collection_memberships: list[
        dict[
            str,
            Any,
        ]
    ] = field(
        default_factory=list,
    )

    activity_events: list[
        dict[
            str,
            Any,
        ]
    ] = field(
        default_factory=list,
    )

    def to_dict(self):

        return {

            "manifest":
                self.manifest
                .to_dict(),

            "sessions":
                list(
                    self.sessions
                ),

            "profiles":
                list(
                    self.profiles
                ),

            "checkpoints":
                list(
                    self.checkpoints
                ),

            "versions":
                list(
                    self.versions
                ),

            "branches":
                list(
                    self.branches
                ),

            "tags":
                list(
                    self.tags
                ),

            "tag_assignments":
                list(
                    self.tag_assignments
                ),

            "collections":
                list(
                    self.collections
                ),

            "collection_memberships":
                list(
                    self.collection_memberships
                ),

            "activity_events":
                list(
                    self.activity_events
                ),
        }

    @classmethod
    def from_dict(

        cls,

        data,

    ):

        return cls(

            manifest=(

                ResearchSnapshotManifest
                .from_dict(

                    data[
                        "manifest"
                    ]
                )
            ),

            sessions=list(

                data.get(

                    "sessions",

                    [],
                )
            ),

            profiles=list(

                data.get(

                    "profiles",

                    [],
                )
            ),

            checkpoints=list(

                data.get(

                    "checkpoints",

                    [],
                )
            ),

            versions=list(

                data.get(

                    "versions",

                    [],
                )
            ),

            branches=list(

                data.get(

                    "branches",

                    [],
                )
            ),

            tags=list(

                data.get(

                    "tags",

                    [],
                )
            ),

            tag_assignments=list(

                data.get(

                    "tag_assignments",

                    [],
                )
            ),

            collections=list(

                data.get(

                    "collections",

                    [],
                )
            ),

            collection_memberships=list(

                data.get(

                    "collection_memberships",

                    [],
                )
            ),

            activity_events=list(

                data.get(

                    "activity_events",

                    [],
                )
            ),
        )
