from dataclasses import (
    dataclass,
)

from .execution_artifact_bundle_manifest_error import (
    ExecutionArtifactBundleManifestError,
)


@dataclass(frozen=True)
class ArtifactBundleManifestEntry:
    """
    Immutable description of a single version grouped into a bundle,
    as recorded in that bundle's manifest.

    Attributes:
        artifact_id: The identifier of the artifact the version
            belongs to
        version_id: The identifier of the version itself
        checksum: The version's recorded integrity checksum
    """

    artifact_id: str

    version_id: str

    checksum: str

    def __post_init__(self):
        self._require_text(self.artifact_id, "artifact ID")
        self._require_text(self.version_id, "version ID")
        self._require_text(self.checksum, "checksum")

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionArtifactBundleManifestError(
                f"Cannot build a bundle manifest entry with an empty or blank {field_name}."
            )
