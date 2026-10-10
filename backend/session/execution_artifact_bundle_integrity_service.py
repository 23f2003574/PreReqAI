from threading import (
    RLock,
)

from .artifact_bundle_integrity import (
    SUPPORTED_ALGORITHMS,
    ArtifactBundleIntegrity,
)

from .execution_artifact_bundle_integrity_error import (
    ExecutionArtifactBundleIntegrityError,
)


class ExecutionArtifactBundleIntegrityService:
    """
    Records and verifies a checksum covering a bundle's complete,
    ordered set of version IDs, using an existing execution artifact
    bundle service to confirm a bundle is known.

    The service's responsibility is checksum bookkeeping only. It
    does not compute checksums itself; a caller is expected to hash a
    bundle's ordered version IDs elsewhere and supply the result here.

    Behavior:
    - A bundle may have at most one recorded checksum; record()
      rejects a bundle that already has one
    - Only SHA256 and SHA512 are supported algorithms
    - verify() is read-only: it never records, overwrites, or
      otherwise mutates a bundle's checksum baseline

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, execution_artifact_bundle_service):
        """
        Args:
            execution_artifact_bundle_service: The registry used to
                confirm a bundle ID is known before a checksum is
                recorded, verified, or looked up for it. Any object
                exposing `get(bundle_id)`, raising if the bundle is
                unknown, is accepted
        """

        self._execution_artifact_bundle_service = execution_artifact_bundle_service
        self._integrity_by_bundle = {}
        self._lock = RLock()

    def record(self, bundle_id: str, checksum: str, algorithm: str = "SHA256") -> ArtifactBundleIntegrity:
        """
        Record the trusted checksum baseline for a bundle.

        Raises:
            ExecutionArtifactBundleIntegrityError: If bundle_id or
                checksum is None or blank, algorithm is not SHA256 or
                SHA512, the execution artifact bundle service does
                not recognize bundle_id, or the bundle already has a
                recorded checksum
        """

        self._validate_id(bundle_id, "bundle ID")
        self._validate_id(checksum, "checksum")

        normalized_algorithm = self._normalize_algorithm(algorithm)

        with self._lock:
            self._ensure_bundle_known(bundle_id)

            if bundle_id in self._integrity_by_bundle:
                raise ExecutionArtifactBundleIntegrityError(
                    f"Bundle ID {bundle_id!r} already has a recorded checksum."
                )

            entry = ArtifactBundleIntegrity(
                bundle_id=bundle_id,
                checksum=checksum,
                algorithm=normalized_algorithm,
            )

            self._integrity_by_bundle[bundle_id] = entry

            return entry

    def verify(self, bundle_id: str, checksum: str) -> bool:
        """
        Compare a candidate checksum against a bundle's recorded
        baseline. Read-only: never mutates recorded state.

        Raises:
            ExecutionArtifactBundleIntegrityError: If bundle_id or
                checksum is None or blank, the execution artifact
                bundle service does not recognize bundle_id, or the
                bundle has no recorded checksum
        """

        self._validate_id(bundle_id, "bundle ID")
        self._validate_id(checksum, "checksum")

        with self._lock:
            self._ensure_bundle_known(bundle_id)

            return self._resolve(bundle_id).checksum == checksum

    def status(self, bundle_id: str) -> ArtifactBundleIntegrity:
        """
        Look up a bundle's recorded checksum baseline.

        Raises:
            ExecutionArtifactBundleIntegrityError: If bundle_id is
                None or blank, the execution artifact bundle service
                does not recognize bundle_id, or the bundle has no
                recorded checksum
        """

        self._validate_id(bundle_id, "bundle ID")

        with self._lock:
            self._ensure_bundle_known(bundle_id)

            return self._resolve(bundle_id)

    def _resolve(self, bundle_id: str) -> ArtifactBundleIntegrity:
        entry = self._integrity_by_bundle.get(bundle_id)

        if entry is None:
            raise ExecutionArtifactBundleIntegrityError(f"No checksum is recorded for bundle ID {bundle_id!r}.")

        return entry

    def _ensure_bundle_known(self, bundle_id: str) -> None:
        try:
            self._execution_artifact_bundle_service.get(bundle_id)
        except Exception as error:
            raise ExecutionArtifactBundleIntegrityError(
                f"No bundle is known under bundle ID {bundle_id!r}."
            ) from error

    @staticmethod
    def _normalize_algorithm(algorithm: str) -> str:
        if algorithm is None or not algorithm.strip():
            raise ExecutionArtifactBundleIntegrityError("Cannot use an empty or blank algorithm.")

        normalized = algorithm.strip().upper()

        if normalized not in SUPPORTED_ALGORITHMS:
            raise ExecutionArtifactBundleIntegrityError(
                f"Unsupported checksum algorithm {algorithm!r}: expected one of {sorted(SUPPORTED_ALGORITHMS)}."
            )

        return normalized

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionArtifactBundleIntegrityError(f"Cannot use an empty or blank {field_name}.")
