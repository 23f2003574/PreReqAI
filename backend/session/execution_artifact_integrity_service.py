from threading import (
    RLock,
)

from .execution_artifact_integrity import (
    SUPPORTED_ALGORITHMS,
    ExecutionArtifactIntegrity,
)

from .execution_artifact_integrity_error import (
    ExecutionArtifactIntegrityError,
)


class ExecutionArtifactIntegrityService:
    """
    Records and verifies content checksums for execution artifact
    versions already known to an execution artifact version service,
    so corruption or unexpected modification can be detected.

    The service's responsibility is checksum bookkeeping only. It
    does not compute checksums or read artifact contents itself; a
    caller is expected to compute a version's checksum elsewhere and
    supply it here.

    Behavior:
    - A version may have at most one recorded checksum; record()
      rejects a version that already has one
    - Only SHA256 and SHA512 are supported algorithms
    - verify() is read-only: it never records, overwrites, or
      otherwise mutates a version's checksum baseline

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self):
        self._integrity_by_version = {}
        self._lock = RLock()

    def record(self, version_id: str, checksum: str, algorithm: str = "SHA256") -> ExecutionArtifactIntegrity:
        """
        Record the trusted checksum baseline for a version.

        Raises:
            ExecutionArtifactIntegrityError: If version_id or
                checksum is None or blank, algorithm is not SHA256 or
                SHA512, or the version already has a recorded
                checksum
        """

        self._validate_id(version_id, "version ID")
        self._validate_id(checksum, "checksum")

        normalized_algorithm = self._normalize_algorithm(algorithm)

        with self._lock:
            if version_id in self._integrity_by_version:
                raise ExecutionArtifactIntegrityError(
                    f"Version ID {version_id!r} already has a recorded checksum."
                )

            entry = ExecutionArtifactIntegrity(
                version_id=version_id,
                checksum=checksum,
                algorithm=normalized_algorithm,
            )

            self._integrity_by_version[version_id] = entry

            return entry

    def verify(self, version_id: str, checksum: str) -> bool:
        """
        Compare a candidate checksum against a version's recorded
        baseline. Read-only: never mutates recorded state.

        Raises:
            ExecutionArtifactIntegrityError: If version_id or
                checksum is None or blank, or the version has no
                recorded checksum
        """

        self._validate_id(version_id, "version ID")
        self._validate_id(checksum, "checksum")

        with self._lock:
            entry = self._resolve(version_id)

            return entry.checksum == checksum

    def status(self, version_id: str) -> ExecutionArtifactIntegrity:
        """
        Look up a version's recorded checksum baseline.

        Raises:
            ExecutionArtifactIntegrityError: If version_id is None or
                blank, or the version has no recorded checksum
        """

        self._validate_id(version_id, "version ID")

        with self._lock:
            return self._resolve(version_id)

    def _resolve(self, version_id: str) -> ExecutionArtifactIntegrity:
        entry = self._integrity_by_version.get(version_id)

        if entry is None:
            raise ExecutionArtifactIntegrityError(
                f"No checksum is recorded for version ID {version_id!r}."
            )

        return entry

    @staticmethod
    def _normalize_algorithm(algorithm: str) -> str:
        if algorithm is None or not algorithm.strip():
            raise ExecutionArtifactIntegrityError("Cannot use an empty or blank algorithm.")

        normalized = algorithm.strip().upper()

        if normalized not in SUPPORTED_ALGORITHMS:
            raise ExecutionArtifactIntegrityError(
                f"Unsupported checksum algorithm {algorithm!r}: expected one of {sorted(SUPPORTED_ALGORITHMS)}."
            )

        return normalized

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionArtifactIntegrityError(f"Cannot use an empty or blank {field_name}.")
