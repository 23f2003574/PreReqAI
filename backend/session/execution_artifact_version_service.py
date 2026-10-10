from threading import (
    RLock,
)

from .execution_artifact_version import (
    ExecutionArtifactVersion,
)

from .execution_artifact_version_error import (
    ExecutionArtifactVersionError,
)


class ExecutionArtifactVersionService:
    """
    Tracks immutable versions of execution artifacts already known to
    an execution artifact registry, so an update never overwrites a
    prior version's output.

    The service's responsibility is version bookkeeping only. It
    does not create or store artifacts themselves; it relies on the
    existing execution artifact registry, given at construction
    time, only to confirm an artifact ID is genuinely known before a
    version is created for it.

    Behavior:
    - A new version starts at 1 and increases by 1 for each version
      created after it
    - latest() returns the highest version number an artifact has,
      without a caller having to track version numbers itself
    - Every version, once created, is immutable and remains in an
      artifact's history forever
    - A version number may not be reused for the same artifact

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, execution_artifact_service):
        """
        Args:
            execution_artifact_service: The registry used to confirm
                an artifact ID is known before a version is created
                for it. Any object exposing `get(artifact_id)`,
                raising if the artifact is unknown, is accepted
        """

        self._execution_artifact_service = execution_artifact_service
        self._versions_by_artifact = {}
        self._lock = RLock()

    def create(self, artifact_id: str, location: str, version: int | None = None) -> ExecutionArtifactVersion:
        """
        Create a new immutable version for an artifact.

        Args:
            artifact_id: The artifact this version belongs to
            location: Where this version's contents can be found
            version: The version number to create it under. If
                omitted, the next number after the artifact's current
                highest version is used, starting at 1

        Raises:
            ExecutionArtifactVersionError: If artifact_id or location
                is None or blank, the execution artifact registry
                does not recognize artifact_id, or the resolved
                version number is already taken for the artifact
        """

        self._validate_id(artifact_id, "artifact ID")
        self._validate_id(location, "location")

        with self._lock:
            self._ensure_artifact_known(artifact_id)

            versions = self._versions_by_artifact.setdefault(artifact_id, {})

            next_version = version if version is not None else (max(versions, default=0) + 1)

            if next_version in versions:
                raise ExecutionArtifactVersionError(
                    f"Version {next_version} already exists for artifact ID {artifact_id!r}."
                )

            entry = ExecutionArtifactVersion(
                artifact_id=artifact_id,
                version=next_version,
                location=location,
            )

            versions[next_version] = entry

            return entry

    def get(self, artifact_id: str, version: int) -> ExecutionArtifactVersion:
        """
        Look up a single version of an artifact.

        Raises:
            ExecutionArtifactVersionError: If artifact_id is None or
                blank, the execution artifact registry does not
                recognize artifact_id, or no such version exists
        """

        self._validate_id(artifact_id, "artifact ID")

        with self._lock:
            self._ensure_artifact_known(artifact_id)

            return self._resolve(artifact_id, version)

    def latest(self, artifact_id: str) -> ExecutionArtifactVersion:
        """
        Look up an artifact's highest-numbered version.

        Raises:
            ExecutionArtifactVersionError: If artifact_id is None or
                blank, the execution artifact registry does not
                recognize artifact_id, or the artifact has no
                versions yet
        """

        self._validate_id(artifact_id, "artifact ID")

        with self._lock:
            self._ensure_artifact_known(artifact_id)

            versions = self._versions_by_artifact.get(artifact_id, {})

            if not versions:
                raise ExecutionArtifactVersionError(f"Artifact ID {artifact_id!r} has no versions.")

            return versions[max(versions)]

    def history(self, artifact_id: str) -> list:
        """
        List every version of an artifact, oldest to newest.

        Raises:
            ExecutionArtifactVersionError: If artifact_id is None or
                blank, or the execution artifact registry does not
                recognize artifact_id
        """

        self._validate_id(artifact_id, "artifact ID")

        with self._lock:
            self._ensure_artifact_known(artifact_id)

            versions = self._versions_by_artifact.get(artifact_id, {})

            return [versions[number] for number in sorted(versions)]

    def _resolve(self, artifact_id: str, version: int) -> ExecutionArtifactVersion:
        entry = self._versions_by_artifact.get(artifact_id, {}).get(version)

        if entry is None:
            raise ExecutionArtifactVersionError(
                f"No version {version!r} is known for artifact ID {artifact_id!r}."
            )

        return entry

    def _ensure_artifact_known(self, artifact_id: str) -> None:
        try:
            self._execution_artifact_service.get(artifact_id)
        except Exception as error:
            raise ExecutionArtifactVersionError(
                f"No artifact is known under artifact ID {artifact_id!r}."
            ) from error

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionArtifactVersionError(f"Cannot use an empty or blank {field_name}.")
