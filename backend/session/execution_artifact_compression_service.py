from dataclasses import (
    replace,
)

from threading import (
    RLock,
)

from .execution_artifact_compression import (
    ExecutionArtifactCompression,
)

from .execution_artifact_compression_error import (
    ExecutionArtifactCompressionError,
)


class ExecutionArtifactCompressionService:
    """
    Compresses registered execution artifacts to reduce transfer size
    and verifies their compression state before distribution, using
    an existing execution artifact registry to confirm an artifact is
    genuinely known before it is compressed.

    The service's responsibility is compression bookkeeping only. It
    does not compress or decompress artifact contents itself, and it
    never modifies the artifact's own recorded metadata; an
    artifact's size is derived read-only from its registered
    location.

    Behavior:
    - An artifact may only be compressed once it is registered
    - GZIP is the only supported algorithm
    - Compression is reversible: restore() always returns an artifact
      to its uncompressed state, and original_size survives a restore
      so the artifact may be compressed again later
    - verify() is the gate a distribution flow calls before sending an
      artifact: it raises unless the artifact is currently compressed,
      enforcing that distribution may require a compressed artifact

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, execution_artifact_service):
        """
        Args:
            execution_artifact_service: The registry used to confirm
                an artifact ID is known, and to look up the artifact
                whose location size is compressed. Any object
                exposing `get(artifact_id)` (returning an object with
                a `.location`), raising if the artifact is unknown,
                is accepted
        """

        self._execution_artifact_service = execution_artifact_service
        self._compression_by_artifact = {}
        self._lock = RLock()

    def compress(self, artifact_id: str) -> ExecutionArtifactCompression:
        """
        Compress a registered artifact using GZIP.

        Raises:
            ExecutionArtifactCompressionError: If artifact_id is None
                or blank, or the execution artifact registry does not
                recognize artifact_id
        """

        self._validate_id(artifact_id, "artifact ID")

        with self._lock:
            artifact = self._get_artifact(artifact_id)
            original_size = self._measure(artifact)
            compressed_size = max(1, original_size // 2)

            compression = ExecutionArtifactCompression(
                artifact_id=artifact_id,
                original_size=original_size,
                compressed_size=compressed_size,
                compressed=True,
            )

            self._compression_by_artifact[artifact_id] = compression

            return compression

    def verify(self, artifact_id: str) -> bool:
        """
        Confirm an artifact is currently compressed, as required
        before it may be distributed under a policy that requires it.

        Raises:
            ExecutionArtifactCompressionError: If artifact_id is None
                or blank, or the artifact is not currently compressed
                (never compressed, or since restored)
        """

        self._validate_id(artifact_id, "artifact ID")

        with self._lock:
            compression = self._compression_by_artifact.get(artifact_id)

            if compression is None or not compression.compressed:
                raise ExecutionArtifactCompressionError(
                    f"Cannot distribute artifact ID {artifact_id!r}: it is not currently compressed."
                )

            return True

    def restore(self, artifact_id: str) -> ExecutionArtifactCompression:
        """
        Restore a currently compressed artifact to its uncompressed
        state. original_size is preserved.

        Raises:
            ExecutionArtifactCompressionError: If artifact_id is None
                or blank, or the artifact is not currently compressed
        """

        self._validate_id(artifact_id, "artifact ID")

        with self._lock:
            compression = self._resolve(artifact_id)

            if not compression.compressed:
                raise ExecutionArtifactCompressionError(
                    f"Cannot restore artifact ID {artifact_id!r}: it is not currently compressed."
                )

            restored = replace(compression, compressed=False, compressed_size=None)
            self._compression_by_artifact[artifact_id] = restored

            return restored

    def status(self, artifact_id: str) -> ExecutionArtifactCompression:
        """
        Look up an artifact's current compression record.

        Raises:
            ExecutionArtifactCompressionError: If artifact_id is None
                or blank, or no compression has ever been recorded
                for it
        """

        self._validate_id(artifact_id, "artifact ID")

        with self._lock:
            return self._resolve(artifact_id)

    @staticmethod
    def _measure(artifact) -> int:
        return len(artifact.location.encode("utf-8"))

    def _resolve(self, artifact_id: str) -> ExecutionArtifactCompression:
        compression = self._compression_by_artifact.get(artifact_id)

        if compression is None:
            raise ExecutionArtifactCompressionError(
                f"No compression has been recorded for artifact ID {artifact_id!r}."
            )

        return compression

    def _get_artifact(self, artifact_id: str):
        try:
            return self._execution_artifact_service.get(artifact_id)
        except Exception as error:
            raise ExecutionArtifactCompressionError(
                f"No artifact is known under artifact ID {artifact_id!r}."
            ) from error

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionArtifactCompressionError(f"Cannot use an empty or blank {field_name}.")
