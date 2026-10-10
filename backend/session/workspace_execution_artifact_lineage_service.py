from threading import (
    RLock,
)

from .workspace_execution_artifact_lineage import (
    WorkspaceExecutionArtifactLineage,
)

from .workspace_execution_artifact_lineage_error import (
    WorkspaceExecutionArtifactLineageError,
)


class WorkspaceExecutionArtifactLineageService:
    """
    Tracks which runtime, artifact, and parent artifact version
    produced each artifact version, using an existing execution
    artifact registry and version service as the sources of truth for
    which artifacts and versions genuinely exist.

    The service's responsibility is lineage bookkeeping only. It does
    not create artifacts or versions itself.

    Behavior:
    - record() admits at most one lineage record per version_id;
      recording again for the same version_id is rejected, preserving
      each relationship as immutable once written
    - A version may not be recorded as its own parent
    - parents() lists an artifact's own lineage records that
      reference a parent
    - children() lists the lineage records recorded for versions that
      consumed one of an artifact's versions as their parent
    - trace() walks the parent chain from a version back to its root,
      raising if the chain revisits a version it has already seen
    - root() returns the version_id of the ultimate ancestor in a
      version's parent chain

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, artifact_registry_service, version_service):
        """
        Args:
            artifact_registry_service: The registry used to confirm
                an artifact ID is known and active. Any object
                exposing `get(artifact_id)`, raising if the artifact
                is unknown or removed, is accepted
            version_service: The service used to confirm a version ID
                belongs to a known artifact. Any object exposing
                `history(artifact_id)` (returning an iterable of
                objects with `.version_id`) is accepted
        """

        self._artifact_registry_service = artifact_registry_service
        self._version_service = version_service
        self._lineage_by_version = {}
        self._lock = RLock()

    def record(
        self,
        artifact_id: str,
        version_id: str,
        runtime_id: str,
        parent_artifact_id: str = None,
        parent_version_id: str = None,
    ) -> WorkspaceExecutionArtifactLineage:
        """
        Record which runtime and parent artifact version produced
        version_id.

        Raises:
            WorkspaceExecutionArtifactLineageError: If artifact_id,
                version_id, or runtime_id is None or blank, only one
                of parent_artifact_id/parent_version_id is given,
                artifact_id or parent_artifact_id is unknown,
                version_id or parent_version_id does not belong to its
                artifact, parent_version_id equals version_id, or a
                lineage record has already been recorded for
                version_id
        """

        self._validate_id(artifact_id, "artifact ID")
        self._validate_id(version_id, "version ID")
        self._validate_id(runtime_id, "runtime ID")

        with self._lock:
            if version_id in self._lineage_by_version:
                raise WorkspaceExecutionArtifactLineageError(
                    f"Lineage has already been recorded for version ID {version_id!r}."
                )

            self._ensure_version_known(artifact_id, version_id)

            if parent_artifact_id is not None or parent_version_id is not None:
                self._validate_id(parent_artifact_id, "parent artifact ID")
                self._validate_id(parent_version_id, "parent version ID")
                self._ensure_version_known(parent_artifact_id, parent_version_id)

            record = WorkspaceExecutionArtifactLineage(
                artifact_id=artifact_id,
                version_id=version_id,
                runtime_id=runtime_id,
                parent_artifact_id=parent_artifact_id,
                parent_version_id=parent_version_id,
            )

            self._lineage_by_version[version_id] = record

            return record

    def parents(self, artifact_id: str) -> tuple:
        """
        List artifact_id's own lineage records that reference a
        parent, in the order they were recorded.

        Raises:
            WorkspaceExecutionArtifactLineageError: If artifact_id is
                None or blank, or the artifact registry does not
                recognize artifact_id as active
        """

        self._validate_id(artifact_id, "artifact ID")

        with self._lock:
            self._ensure_artifact_known(artifact_id)

            return tuple(
                record
                for record in self._lineage_by_version.values()
                if record.artifact_id == artifact_id and record.parent_artifact_id is not None
            )

    def children(self, artifact_id: str) -> tuple:
        """
        List the lineage records for versions that consumed one of
        artifact_id's versions as their parent, in the order they
        were recorded.

        Raises:
            WorkspaceExecutionArtifactLineageError: If artifact_id is
                None or blank, or the artifact registry does not
                recognize artifact_id as active
        """

        self._validate_id(artifact_id, "artifact ID")

        with self._lock:
            self._ensure_artifact_known(artifact_id)

            return tuple(
                record for record in self._lineage_by_version.values() if record.parent_artifact_id == artifact_id
            )

    def trace(self, version_id: str) -> tuple:
        """
        Walk the parent chain from version_id back to its root.

        Returns:
            A tuple of lineage records starting with version_id's own
            record and ending with the root's record

        Raises:
            WorkspaceExecutionArtifactLineageError: If version_id is
                None or blank, no lineage record exists for
                version_id, or the parent chain revisits a version
                already seen
        """

        self._validate_id(version_id, "version ID")

        with self._lock:
            chain = []
            seen = set()
            current = version_id

            while True:
                record = self._lineage_by_version.get(current)

                if record is None:
                    raise WorkspaceExecutionArtifactLineageError(
                        f"No lineage record exists for version ID {current!r}."
                    )

                if current in seen:
                    raise WorkspaceExecutionArtifactLineageError(
                        f"Cycle detected in lineage while tracing version ID {version_id!r}."
                    )

                seen.add(current)
                chain.append(record)

                if record.parent_version_id is None:
                    break

                current = record.parent_version_id

            return tuple(chain)

    def root(self, version_id: str) -> str:
        """
        The version_id of the ultimate ancestor in version_id's
        parent chain.

        Raises:
            WorkspaceExecutionArtifactLineageError: If version_id is
                None or blank, no lineage record exists for
                version_id, or its parent chain contains a cycle
        """

        return self.trace(version_id)[-1].version_id

    def _ensure_artifact_known(self, artifact_id: str) -> None:
        try:
            self._artifact_registry_service.get(artifact_id)
        except Exception as error:
            raise WorkspaceExecutionArtifactLineageError(
                f"No active artifact is known under artifact ID {artifact_id!r}."
            ) from error

    def _ensure_version_known(self, artifact_id: str, version_id: str) -> None:
        self._ensure_artifact_known(artifact_id)

        try:
            versions = self._version_service.history(artifact_id)
        except Exception as error:
            raise WorkspaceExecutionArtifactLineageError(
                f"No version history is available for artifact ID {artifact_id!r}."
            ) from error

        if not any(version.version_id == version_id for version in versions):
            raise WorkspaceExecutionArtifactLineageError(
                f"No version is known under version ID {version_id!r} for artifact ID {artifact_id!r}."
            )

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise WorkspaceExecutionArtifactLineageError(f"Cannot use an empty or blank {field_name}.")
