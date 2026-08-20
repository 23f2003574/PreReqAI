from threading import (
    RLock,
)

from .workspace_execution_artifact_metadata import (
    WorkspaceExecutionArtifactMetadata,
)

from .workspace_execution_artifact_metadata_error import (
    WorkspaceExecutionArtifactMetadataError,
)


class WorkspaceExecutionArtifactMetadataService:
    """
    Attaches structured, searchable key/value metadata to workspace
    execution artifacts already known to an execution artifact
    registry.

    The service's responsibility is metadata bookkeeping only. It
    does not create or store artifacts themselves; it relies on the
    existing execution artifact registry, given at construction time,
    only to confirm an artifact ID is genuinely known and active
    before metadata is attached to, read from, or removed from it.

    Behavior:
    - set() overwrites any existing value already set under the same
      key for an artifact, refreshing its updated_at
    - get()/all()/remove() require the key (or artifact) to already
      hold an entry
    - search() finds every entry, across every artifact, currently
      set to an exact key/value pair

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, artifact_registry_service):
        """
        Args:
            artifact_registry_service: The registry used to confirm
                an artifact ID is known and active before metadata is
                attached to, read from, or removed from it. Any
                object exposing `get(artifact_id)`, raising if the
                artifact is unknown or removed, is accepted
        """

        self._artifact_registry_service = artifact_registry_service
        self._metadata_by_artifact = {}
        self._lock = RLock()

    def set(self, artifact_id: str, key: str, value) -> WorkspaceExecutionArtifactMetadata:
        """
        Set a metadata entry for an artifact, overwriting any value
        already set under the same key.

        Raises:
            WorkspaceExecutionArtifactMetadataError: If artifact_id or
                key is None or blank, or the artifact registry does
                not recognize artifact_id as active
        """

        self._validate_text(artifact_id, "artifact ID")
        self._validate_text(key, "key")

        with self._lock:
            self._ensure_artifact_known(artifact_id)

            entry = WorkspaceExecutionArtifactMetadata(artifact_id=artifact_id, key=key, value=value)

            self._metadata_by_artifact.setdefault(artifact_id, {})[key] = entry

            return entry

    def get(self, artifact_id: str, key: str) -> WorkspaceExecutionArtifactMetadata:
        """
        Look up a single metadata entry for an artifact.

        Raises:
            WorkspaceExecutionArtifactMetadataError: If artifact_id or
                key is None or blank, the artifact registry does not
                recognize artifact_id as active, or no value is set
                under key
        """

        self._validate_text(artifact_id, "artifact ID")
        self._validate_text(key, "key")

        with self._lock:
            self._ensure_artifact_known(artifact_id)

            return self._resolve(artifact_id, key)

    def all(self, artifact_id: str) -> tuple:
        """
        Every metadata entry currently set for an artifact.

        Raises:
            WorkspaceExecutionArtifactMetadataError: If artifact_id is
                None or blank, or the artifact registry does not
                recognize artifact_id as active
        """

        self._validate_text(artifact_id, "artifact ID")

        with self._lock:
            self._ensure_artifact_known(artifact_id)

            return tuple(self._metadata_by_artifact.get(artifact_id, {}).values())

    def remove(self, artifact_id: str, key: str) -> WorkspaceExecutionArtifactMetadata:
        """
        Remove a metadata entry from an artifact.

        Raises:
            WorkspaceExecutionArtifactMetadataError: If artifact_id or
                key is None or blank, the artifact registry does not
                recognize artifact_id as active, or no value is set
                under key
        """

        self._validate_text(artifact_id, "artifact ID")
        self._validate_text(key, "key")

        with self._lock:
            self._ensure_artifact_known(artifact_id)

            entry = self._resolve(artifact_id, key)

            del self._metadata_by_artifact[artifact_id][key]

            return entry

    def search(self, key: str, value) -> tuple:
        """
        Every metadata entry, across every artifact, currently set to
        an exact key/value pair.

        Raises:
            WorkspaceExecutionArtifactMetadataError: If key is None or
                blank
        """

        self._validate_text(key, "key")

        with self._lock:
            return tuple(
                entry
                for entries in self._metadata_by_artifact.values()
                for entry in entries.values()
                if entry.key == key and entry.value == value
            )

    def _resolve(self, artifact_id: str, key: str) -> WorkspaceExecutionArtifactMetadata:
        entry = self._metadata_by_artifact.get(artifact_id, {}).get(key)

        if entry is None:
            raise WorkspaceExecutionArtifactMetadataError(
                f"No metadata is set under key {key!r} for artifact ID {artifact_id!r}."
            )

        return entry

    def _ensure_artifact_known(self, artifact_id: str) -> None:
        try:
            self._artifact_registry_service.get(artifact_id)
        except Exception as error:
            raise WorkspaceExecutionArtifactMetadataError(
                f"No active artifact is known under artifact ID {artifact_id!r}."
            ) from error

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise WorkspaceExecutionArtifactMetadataError(f"Cannot use an empty or blank {field_name}.")
