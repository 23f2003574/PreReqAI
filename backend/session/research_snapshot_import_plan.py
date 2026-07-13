from dataclasses import (
    dataclass,
    field,
)

from typing import (
    Any,
)

from .research_snapshot_identity_map import (
    ResearchSnapshotIdentityMap,
)

from .research_snapshot_import_conflict import (
    ResearchSnapshotImportConflict,
)

from .research_snapshot_import_strategy import (
    ResearchSnapshotImportStrategy,
)


@dataclass
class ResearchSnapshotImportPlan:
    """
    Immutable-style preview of everything
    an import would create locally.
    """

    snapshot_id: str

    strategy: (
        ResearchSnapshotImportStrategy
    )

    identity_map: (
        ResearchSnapshotIdentityMap
    )

    conflicts: list[
        ResearchSnapshotImportConflict
    ] = field(
        default_factory=list,
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

    @property
    def has_conflicts(self):

        return bool(
            self.conflicts
        )

    def to_dict(self):

        return {

            "snapshot_id":
                self.snapshot_id,

            "strategy":
                self.strategy.value,

            "identity_map":
                self.identity_map
                .to_dict(),

            "conflicts": [

                conflict.to_dict()

                for conflict

                in self.conflicts
            ],

            "counts": {

                "sessions":
                    len(
                        self.sessions
                    ),

                "profiles":
                    len(
                        self.profiles
                    ),

                "checkpoints":
                    len(
                        self.checkpoints
                    ),

                "versions":
                    len(
                        self.versions
                    ),

                "branches":
                    len(
                        self.branches
                    ),

                "tags":
                    len(
                        self.tags
                    ),

                "tag_assignments":
                    len(
                        self.tag_assignments
                    ),

                "collections":
                    len(
                        self.collections
                    ),

                "collection_memberships":
                    len(
                        self.collection_memberships
                    ),

                "activity_events":
                    len(
                        self.activity_events
                    ),
            },
        }
