from dataclasses import (
    dataclass,
)


@dataclass
class ResearchSnapshotImportConflict:
    """
    Describes one identity conflict between
    an imported snapshot and local state.
    """

    entity_type: str

    imported_id: str

    existing_id: str

    resolution: (
        str | None
    ) = None

    remapped_id: (
        str | None
    ) = None

    def to_dict(self):

        return {

            "entity_type":
                self.entity_type,

            "imported_id":
                self.imported_id,

            "existing_id":
                self.existing_id,

            "resolution":
                self.resolution,

            "remapped_id":
                self.remapped_id,
        }
