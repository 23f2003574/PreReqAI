from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from uuid import uuid4

from .execution_artifact_manifest_error import (
    ExecutionArtifactManifestError,
)


@dataclass(frozen=True)
class ExecutionArtifactManifest:
    """
    Immutable snapshot describing an artifact's complete version set
    and metadata at the moment the manifest was generated.

    The manifest is a value object only. It performs no persistence
    of its own; generating, retrieving, verifying, and listing
    manifests is the responsibility of an execution artifact manifest
    service, which produces a new snapshot for every generation
    rather than mutating an existing one.

    Attributes:
        manifest_id: The manifest's unique identifier
        artifact_id: The identifier of the execution artifact this
            manifest describes
        versions: The artifact's versions at generation time, ordered
            oldest to newest
        metadata: The artifact's metadata entries at generation time,
            ordered deterministically by key
        generated_at: When this manifest was generated
        checksum: A deterministic checksum covering artifact_id,
            versions, and metadata
    """

    artifact_id: str

    versions: tuple

    metadata: tuple

    checksum: str

    manifest_id: str = field(
        default_factory=lambda: str(uuid4()),
    )

    generated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    def __post_init__(self):
        self._require_text(self.manifest_id, "manifest ID")
        self._require_text(self.artifact_id, "artifact ID")
        self._require_text(self.checksum, "checksum")

        if not isinstance(self.versions, tuple):
            raise ExecutionArtifactManifestError(
                "Cannot build an execution artifact manifest with non-tuple versions."
            )

        if not isinstance(self.metadata, tuple):
            raise ExecutionArtifactManifestError(
                "Cannot build an execution artifact manifest with non-tuple metadata."
            )

        if not isinstance(self.generated_at, datetime):
            raise ExecutionArtifactManifestError(
                "Cannot build an execution artifact manifest with a non-datetime generated_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionArtifactManifestError(
                f"Cannot build an execution artifact manifest with an empty or blank {field_name}."
            )
