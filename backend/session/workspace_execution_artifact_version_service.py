from threading import (
    RLock,
)

from .workspace_execution_artifact_version import (
    WorkspaceExecutionArtifactVersion,
)

from .workspace_execution_artifact_version_error import (
    WorkspaceExecutionArtifactVersionError,
)


class WorkspaceExecutionArtifactVersionService:
    """
    Tracks immutable versions of workspace execution artifacts
    already known to an execution artifact registry, so an update
    never overwrites a prior version's output.

    The service's responsibility is version bookkeeping only. It
    does not create or store artifacts themselves; it relies on the
    existing execution artifact registry, given at construction
    time, only to confirm an artifact ID is genuinely known and
    active before a version is created for it.

    Behavior:
    - A new version starts at 1 and increases by 1 for each version
      created after it; version numbers strictly increase and are
      never reused or skipped backwards
    - Every version, once created, is immutable and remains in an
      artifact's history forever
    - latest() returns the highest version number an artifact has
    - history() lists every version, oldest to newest

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, artifact_registry_service):
        """
        Args:
            artifact_registry_service: The registry used to confirm
                an artifact ID is known and active before a version
                is created for it. Any object exposing
                `get(artifact_id)`, raising if the artifact is
                unknown or removed, is accepted
        """

        self._artifact_registry_service = artifact_registry_service
        self._versions_by_artifact = {}
        self._lock = RLock()

    def create(self, artifact_id: str, location: str, checksum: str) -> WorkspaceExecutionArtifactVersion:
        """
        Create the next immutable version for an artifact.

        Raises:
            WorkspaceExecutionArtifactVersionError: If artifact_id,
                location, or checksum is None or blank, or the
                artifact registry does not recognize artifact_id as
                active
        """

        self._validate_text(artifact_id, "artifact ID")
        self._validate_text(location, "location")
        self._validate_text(checksum, "checksum")

        with self._lock:
            self._ensure_artifact_known(artifact_id)

            versions = self._versions_by_artifact.setdefault(artifact_id, {})

            next_version = max(versions, default=0) + 1

            entry = WorkspaceExecutionArtifactVersion(
                artifact_id=artifact_id,
                version=next_version,
                location=location,
                checksum=checksum,
            )

            versions[next_version] = entry

            return entry

    def get(self, artifact_id: str, version: int) -> WorkspaceExecutionArtifactVersion:
        """
        Look up a single version of an artifact.

        Raises:
            WorkspaceExecutionArtifactVersionError: If artifact_id is
                None or blank, the artifact registry does not
                recognize artifact_id as active, or no such version
                exists
        """

        self._validate_text(artifact_id, "artifact ID")

        with self._lock:
            self._ensure_artifact_known(artifact_id)

            return self._resolve(artifact_id, version)

    def latest(self, artifact_id: str) -> WorkspaceExecutionArtifactVersion:
        """
        Look up an artifact's highest-numbered version.

        Raises:
            WorkspaceExecutionArtifactVersionError: If artifact_id is
                None or blank, the artifact registry does not
                recognize artifact_id as active, or the artifact has
                no versions yet
        """

        self._validate_text(artifact_id, "artifact ID")

        with self._lock:
            self._ensure_artifact_known(artifact_id)

            versions = self._versions_by_artifact.get(artifact_id, {})

            if not versions:
                raise WorkspaceExecutionArtifactVersionError(f"Artifact ID {artifact_id!r} has no versions.")

            return versions[max(versions)]

    def history(self, artifact_id: str) -> tuple:
        """
        List every version of an artifact, oldest to newest.

        Raises:
            WorkspaceExecutionArtifactVersionError: If artifact_id is
                None or blank, or the artifact registry does not
                recognize artifact_id as active
        """

        self._validate_text(artifact_id, "artifact ID")

        with self._lock:
            self._ensure_artifact_known(artifact_id)

            versions = self._versions_by_artifact.get(artifact_id, {})

            return tuple(versions[number] for number in sorted(versions))

    def _resolve(self, artifact_id: str, version: int) -> WorkspaceExecutionArtifactVersion:
        entry = self._versions_by_artifact.get(artifact_id, {}).get(version)

        if entry is None:
            raise WorkspaceExecutionArtifactVersionError(
                f"No version {version!r} is known for artifact ID {artifact_id!r}."
            )

        return entry

    def _ensure_artifact_known(self, artifact_id: str) -> None:
        try:
            self._artifact_registry_service.get(artifact_id)
        except Exception as error:
            raise WorkspaceExecutionArtifactVersionError(
                f"No active artifact is known under artifact ID {artifact_id!r}."
            ) from error

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise WorkspaceExecutionArtifactVersionError(f"Cannot use an empty or blank {field_name}.")
