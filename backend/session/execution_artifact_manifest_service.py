import hashlib

from threading import (
    RLock,
)

from .execution_artifact_manifest import (
    ExecutionArtifactManifest,
)

from .execution_artifact_manifest_error import (
    ExecutionArtifactManifestError,
)


class ExecutionArtifactManifestService:
    """
    Generates deterministic manifests describing an artifact's
    complete version set and metadata, using an existing execution
    artifact registry, version service, and metadata service as the
    sources of truth for an artifact's current versions and metadata.

    The service's responsibility is manifest bookkeeping only. It
    does not create versions or metadata itself.

    Behavior:
    - generate() snapshots an artifact's current versions (oldest to
      newest) and metadata (ordered deterministically by key) into a
      new, immutable manifest
    - Two manifests built from the same versions and metadata always
      have the same checksum
    - verify() is read-only: it rebuilds the artifact's manifest from
      its current versions and metadata and compares the resulting
      checksum to a stored manifest's checksum, without recording
      anything
    - history() lists every manifest generated for an artifact, oldest
      to newest

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, artifact_registry_service, version_service, metadata_service):
        """
        Args:
            artifact_registry_service: The registry used to confirm
                an artifact ID is known and active before a manifest
                is generated for it. Any object exposing
                `get(artifact_id)`, raising if the artifact is
                unknown or removed, is accepted
            version_service: The service used to look up an artifact's
                versions. Any object exposing `history(artifact_id)`
                (returning an iterable of objects with `.version` and
                `.checksum`) is accepted
            metadata_service: The service used to look up an
                artifact's metadata. Any object exposing
                `all(artifact_id)` (returning an iterable of objects
                with `.key` and `.value`) is accepted
        """

        self._artifact_registry_service = artifact_registry_service
        self._version_service = version_service
        self._metadata_service = metadata_service
        self._manifests_by_id = {}
        self._manifest_ids_by_artifact = {}
        self._lock = RLock()

    def generate(self, artifact_id: str) -> ExecutionArtifactManifest:
        """
        Generate and store a fresh manifest for an artifact, from its
        current version set and metadata.

        Raises:
            ExecutionArtifactManifestError: If artifact_id is None or
                blank, or the artifact registry does not recognize
                artifact_id as active
        """

        self._validate_id(artifact_id, "artifact ID")

        with self._lock:
            self._ensure_artifact_known(artifact_id)

            manifest = self._build_manifest(artifact_id)

            self._manifests_by_id[manifest.manifest_id] = manifest
            self._manifest_ids_by_artifact.setdefault(artifact_id, []).append(manifest.manifest_id)

            return manifest

    def get(self, manifest_id: str) -> ExecutionArtifactManifest:
        """
        Look up a manifest by ID.

        Raises:
            ExecutionArtifactManifestError: If manifest_id is None or
                blank, or no manifest is registered under it
        """

        self._validate_id(manifest_id, "manifest ID")

        with self._lock:
            return self._resolve(manifest_id)

    def verify(self, manifest_id: str) -> bool:
        """
        Check whether a manifest's artifact still has the same
        versions and metadata it was generated from. Read-only: never
        mutates the stored manifest.

        Raises:
            ExecutionArtifactManifestError: If manifest_id is None or
                blank, or no manifest is registered under it
        """

        self._validate_id(manifest_id, "manifest ID")

        with self._lock:
            stored = self._resolve(manifest_id)
            current = self._build_manifest(stored.artifact_id)

            return current.checksum == stored.checksum

    def history(self, artifact_id: str) -> tuple:
        """
        List every manifest generated for an artifact, oldest to
        newest.

        Raises:
            ExecutionArtifactManifestError: If artifact_id is None or
                blank
        """

        self._validate_id(artifact_id, "artifact ID")

        with self._lock:
            return tuple(
                self._manifests_by_id[manifest_id]
                for manifest_id in self._manifest_ids_by_artifact.get(artifact_id, [])
            )

    def _build_manifest(self, artifact_id: str) -> ExecutionArtifactManifest:
        versions = tuple(self._version_service.history(artifact_id))
        metadata = tuple(sorted(self._metadata_service.all(artifact_id), key=lambda entry: entry.key))

        return ExecutionArtifactManifest(
            artifact_id=artifact_id,
            versions=versions,
            metadata=metadata,
            checksum=self._compute_checksum(artifact_id, versions, metadata),
        )

    @staticmethod
    def _compute_checksum(artifact_id: str, versions, metadata) -> str:
        versions_part = ",".join(f"{version.version}:{version.checksum}" for version in versions)
        metadata_part = ",".join(f"{entry.key}={entry.value!r}" for entry in metadata)

        canonical = f"{artifact_id}|{versions_part}|{metadata_part}"

        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _ensure_artifact_known(self, artifact_id: str) -> None:
        try:
            self._artifact_registry_service.get(artifact_id)
        except Exception as error:
            raise ExecutionArtifactManifestError(
                f"No active artifact is known under artifact ID {artifact_id!r}."
            ) from error

    def _resolve(self, manifest_id: str) -> ExecutionArtifactManifest:
        manifest = self._manifests_by_id.get(manifest_id)

        if manifest is None:
            raise ExecutionArtifactManifestError(f"No manifest is registered under manifest ID {manifest_id!r}.")

        return manifest

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionArtifactManifestError(f"Cannot use an empty or blank {field_name}.")
