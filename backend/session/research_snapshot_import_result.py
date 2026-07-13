from dataclasses import (
    dataclass,
)

from .research_snapshot_identity_map import (
    ResearchSnapshotIdentityMap,
)


@dataclass
class ResearchSnapshotImportResult:
    """
    Describes a successfully completed
    research snapshot import.
    """

    snapshot_id: str

    identity_map: (
        ResearchSnapshotIdentityMap
    )

    imported_sessions: int

    imported_profiles: int

    imported_checkpoints: int

    imported_versions: int

    imported_branches: int

    imported_tags: int

    imported_tag_assignments: int

    imported_collections: int

    imported_collection_memberships: int

    imported_activity_events: int

    def to_dict(self):

        return {

            "snapshot_id":
                self.snapshot_id,

            "identity_map":
                self.identity_map
                .to_dict(),

            "imported_sessions":
                self.imported_sessions,

            "imported_profiles":
                self.imported_profiles,

            "imported_checkpoints":
                self.imported_checkpoints,

            "imported_versions":
                self.imported_versions,

            "imported_branches":
                self.imported_branches,

            "imported_tags":
                self.imported_tags,

            "imported_tag_assignments":
                self.imported_tag_assignments,

            "imported_collections":
                self.imported_collections,

            "imported_collection_memberships":
                self.imported_collection_memberships,

            "imported_activity_events":
                self.imported_activity_events,
        }
