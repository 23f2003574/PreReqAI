from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from .artifact_bundle_manifest_entry import (
    ArtifactBundleManifestEntry,
)

from .execution_artifact_bundle_manifest_error import (
    ExecutionArtifactBundleManifestError,
)


@dataclass(frozen=True)
class ArtifactBundleManifest:
    """
    Immutable, deterministic description of exactly which artifact
    versions belong to a bundle, in bundle order, with each version's
    checksum.

    The manifest is a value object only. It performs no verification
    of its own; generating, retrieving, verifying, and diffing
    manifests is the responsibility of an execution artifact bundle
    manifest service.

    Attributes:
        bundle_id: The identifier of the bundle this manifest
            describes
        entries: The bundle's versions, in bundle order
        generated_at: When this manifest was generated
        fingerprint: A deterministic digest of entries, identical for
            any two manifests with the same entries in the same order
    """

    bundle_id: str

    entries: tuple

    fingerprint: str

    generated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    def __post_init__(self):
        self._require_text(self.bundle_id, "bundle ID")
        self._require_text(self.fingerprint, "fingerprint")

        if self.entries is None:
            raise ExecutionArtifactBundleManifestError("Cannot build a bundle manifest with None entries.")

        entries = tuple(self.entries)

        for entry in entries:
            if not isinstance(entry, ArtifactBundleManifestEntry):
                raise ExecutionArtifactBundleManifestError(
                    "Cannot build a bundle manifest with a non-ArtifactBundleManifestEntry entry."
                )

        object.__setattr__(self, "entries", entries)

        if not isinstance(self.generated_at, datetime):
            raise ExecutionArtifactBundleManifestError(
                "Cannot build a bundle manifest with a non-datetime generated_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionArtifactBundleManifestError(
                f"Cannot build a bundle manifest with an empty or blank {field_name}."
            )
