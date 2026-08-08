from threading import (
    RLock,
)

from .execution_artifact_metadata import (
    ExecutionArtifactMetadata,
)

from .execution_artifact_metadata_error import (
    ExecutionArtifactMetadataError,
)

from .execution_artifact_tag import (
    ExecutionArtifactTag,
)


class ExecutionArtifactMetadataService:
    """
    Attaches searchable key/value metadata and tags to execution
    artifacts already known to an execution artifact registry.

    The service's responsibility is metadata and tag bookkeeping
    only. It does not create or store artifacts themselves; it
    relies on the existing execution artifact registry, given at
    construction time, only to confirm an artifact ID is genuinely
    known before metadata or a tag is attached to it.

    Behavior:
    - set() overwrites any existing value already set under the same
      key for an artifact
    - A tag may only be applied to a given artifact once; applying it
      again is rejected until it is removed
    - find() returns every tag record for artifacts currently tagged
      with the given tag

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, execution_artifact_service):
        """
        Args:
            execution_artifact_service: The registry used to confirm
                an artifact ID is known before metadata or a tag is
                attached to it. Any object exposing `get(artifact_id)`,
                raising if the artifact is unknown, is accepted
        """

        self._execution_artifact_service = execution_artifact_service
        self._metadata_by_artifact = {}
        self._tags_by_artifact = {}
        self._artifact_ids_by_tag = {}
        self._lock = RLock()

    def set(self, artifact_id: str, key: str, value) -> ExecutionArtifactMetadata:
        """
        Set a metadata entry for an artifact, overwriting any value
        already set under the same key.

        Raises:
            ExecutionArtifactMetadataError: If artifact_id or key is
                None or blank, or the execution artifact registry
                does not recognize artifact_id
        """

        self._validate_id(artifact_id, "artifact ID")
        self._validate_id(key, "key")

        with self._lock:
            self._ensure_artifact_known(artifact_id)

            entry = ExecutionArtifactMetadata(artifact_id=artifact_id, key=key, value=value)

            self._metadata_by_artifact.setdefault(artifact_id, {})[key] = entry

            return entry

    def get(self, artifact_id: str, key: str) -> ExecutionArtifactMetadata:
        """
        Look up a single metadata entry for an artifact.

        Raises:
            ExecutionArtifactMetadataError: If artifact_id or key is
                None or blank, the execution artifact registry does
                not recognize artifact_id, or no value is set under
                key
        """

        self._validate_id(artifact_id, "artifact ID")
        self._validate_id(key, "key")

        with self._lock:
            self._ensure_artifact_known(artifact_id)

            return self._resolve_metadata(artifact_id, key)

    def remove(self, artifact_id: str, key: str) -> ExecutionArtifactMetadata:
        """
        Remove a metadata entry from an artifact.

        Raises:
            ExecutionArtifactMetadataError: If artifact_id or key is
                None or blank, the execution artifact registry does
                not recognize artifact_id, or no value is set under
                key
        """

        self._validate_id(artifact_id, "artifact ID")
        self._validate_id(key, "key")

        with self._lock:
            self._ensure_artifact_known(artifact_id)

            entry = self._resolve_metadata(artifact_id, key)

            del self._metadata_by_artifact[artifact_id][key]

            return entry

    def tag(self, artifact_id: str, tag: str) -> ExecutionArtifactTag:
        """
        Apply a tag to an artifact.

        Raises:
            ExecutionArtifactMetadataError: If artifact_id or tag is
                None or blank, the execution artifact registry does
                not recognize artifact_id, or the tag is already
                applied to the artifact
        """

        self._validate_id(artifact_id, "artifact ID")
        self._validate_id(tag, "tag")

        with self._lock:
            self._ensure_artifact_known(artifact_id)

            existing = self._tags_by_artifact.setdefault(artifact_id, {})

            if tag in existing:
                raise ExecutionArtifactMetadataError(
                    f"Tag {tag!r} is already applied to artifact ID {artifact_id!r}."
                )

            entry = ExecutionArtifactTag(artifact_id=artifact_id, tag=tag)

            existing[tag] = entry
            self._artifact_ids_by_tag.setdefault(tag, []).append(artifact_id)

            return entry

    def tags(self, artifact_id: str) -> list:
        """
        List every tag currently applied to an artifact, in the
        order they were applied.

        Raises:
            ExecutionArtifactMetadataError: If artifact_id is None or
                blank, or the execution artifact registry does not
                recognize artifact_id
        """

        self._validate_id(artifact_id, "artifact ID")

        with self._lock:
            self._ensure_artifact_known(artifact_id)

            return list(self._tags_by_artifact.get(artifact_id, {}).values())

    def find(self, tag: str) -> list:
        """
        List every tag record for artifacts currently tagged with
        the given tag, in the order they were tagged.

        Raises:
            ExecutionArtifactMetadataError: If tag is None or blank
        """

        self._validate_id(tag, "tag")

        with self._lock:
            return [
                self._tags_by_artifact[artifact_id][tag]
                for artifact_id in self._artifact_ids_by_tag.get(tag, [])
            ]

    def _resolve_metadata(self, artifact_id: str, key: str) -> ExecutionArtifactMetadata:
        entry = self._metadata_by_artifact.get(artifact_id, {}).get(key)

        if entry is None:
            raise ExecutionArtifactMetadataError(
                f"No metadata is set under key {key!r} for artifact ID {artifact_id!r}."
            )

        return entry

    def _ensure_artifact_known(self, artifact_id: str) -> None:
        try:
            self._execution_artifact_service.get(artifact_id)
        except Exception as error:
            raise ExecutionArtifactMetadataError(
                f"No artifact is known under artifact ID {artifact_id!r}."
            ) from error

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionArtifactMetadataError(f"Cannot use an empty or blank {field_name}.")
