from threading import (
    RLock,
)

from .workspace_execution_artifact_integrity import (
    STATUS_CORRUPT,
    STATUS_VERIFIED,
    WorkspaceExecutionArtifactIntegrity,
)

from .workspace_execution_artifact_integrity_error import (
    WorkspaceExecutionArtifactIntegrityError,
)


class WorkspaceExecutionArtifactIntegrityService:
    """
    Verifies that execution artifact versions have not changed since
    registration, using an existing version resolver for a version's
    recorded checksum baseline and a checksum provider for its actual,
    current checksum.

    The service's responsibility is comparison and history
    bookkeeping only. It does not compute checksums or read artifact
    contents itself.

    Behavior:
    - check() always compares the exact expected and actual checksums
      and records the outcome, marking any mismatch CORRUPT; it never
      silently accepts corruption as a match
    - verify() performs the same comparison but is read-only: it
      never records a check to history
    - history() lists every check recorded for an artifact's
      versions, oldest to newest
    - Repeated checks against unchanged content always produce the
      same status

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, version_resolver, checksum_provider):
        """
        Args:
            version_resolver: The resolver used to look up a
                version's recorded checksum baseline. Any object
                exposing `resolve(version_id)` (returning an object
                with `.artifact_id` and `.checksum`), raising if the
                version is unknown, is accepted
            checksum_provider: The provider used to compute a
                version's actual, current checksum. Any object
                exposing `checksum(version_id) -> str` is accepted
        """

        self._version_resolver = version_resolver
        self._checksum_provider = checksum_provider
        self._checks_by_artifact = {}
        self._lock = RLock()

    def check(self, version_id: str) -> WorkspaceExecutionArtifactIntegrity:
        """
        Compare version_id's actual checksum against its expected
        checksum baseline and record the outcome.

        Raises:
            WorkspaceExecutionArtifactIntegrityError: If version_id is
                None or blank, or the version resolver does not
                recognize version_id
        """

        self._validate_id(version_id, "version ID")

        with self._lock:
            entry = self._build_check(version_id)

            self._checks_by_artifact.setdefault(entry.artifact_id, []).append(entry)

            return entry

    def verify(self, version_id: str) -> bool:
        """
        Compare version_id's actual checksum against its expected
        checksum baseline. Read-only: never records a check to
        history.

        Raises:
            WorkspaceExecutionArtifactIntegrityError: If version_id is
                None or blank, or the version resolver does not
                recognize version_id
        """

        self._validate_id(version_id, "version ID")

        with self._lock:
            return self._build_check(version_id).status == STATUS_VERIFIED

    def history(self, artifact_id: str) -> tuple:
        """
        List every check recorded for any version of artifact_id,
        oldest to newest.

        Raises:
            WorkspaceExecutionArtifactIntegrityError: If artifact_id
                is None or blank
        """

        self._validate_id(artifact_id, "artifact ID")

        with self._lock:
            return tuple(self._checks_by_artifact.get(artifact_id, ()))

    def _build_check(self, version_id: str) -> WorkspaceExecutionArtifactIntegrity:
        version = self._resolve_version(version_id)
        actual_checksum = self._resolve_checksum(version_id)

        status = STATUS_VERIFIED if version.checksum == actual_checksum else STATUS_CORRUPT

        return WorkspaceExecutionArtifactIntegrity(
            artifact_id=version.artifact_id,
            version_id=version_id,
            expected_checksum=version.checksum,
            actual_checksum=actual_checksum,
            status=status,
        )

    def _resolve_version(self, version_id: str):
        try:
            return self._version_resolver.resolve(version_id)
        except Exception as error:
            raise WorkspaceExecutionArtifactIntegrityError(
                f"No version is known under version ID {version_id!r}."
            ) from error

    def _resolve_checksum(self, version_id: str) -> str:
        try:
            return self._checksum_provider.checksum(version_id)
        except Exception as error:
            raise WorkspaceExecutionArtifactIntegrityError(
                f"Cannot compute an actual checksum for version ID {version_id!r}."
            ) from error

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise WorkspaceExecutionArtifactIntegrityError(f"Cannot use an empty or blank {field_name}.")
