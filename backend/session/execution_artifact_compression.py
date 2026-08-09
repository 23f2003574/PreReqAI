from dataclasses import (
    dataclass,
)

from typing import Optional

from .execution_artifact_compression_error import (
    ExecutionArtifactCompressionError,
)

SUPPORTED_ALGORITHMS = frozenset(
    {
        "GZIP",
    }
)


@dataclass(frozen=True)
class ExecutionArtifactCompression:
    """
    Immutable record of an execution artifact's current compression
    state, used to verify it is compressed before it may be
    distributed under a policy that requires it.

    The compression record is a value object only. It performs no
    compression of its own; compressing, verifying, restoring, and
    looking up an artifact's compression state is the responsibility
    of an execution artifact compression service. It never affects
    the artifact's own recorded metadata.

    Attributes:
        artifact_id: The identifier of the execution artifact this
            record describes
        original_size: The artifact's size, in bytes, before
            compression; preserved even after the artifact is
            restored
        algorithm: The compression algorithm used, currently always
            GZIP
        compressed_size: The artifact's size, in bytes, after
            compression, or None if it is not currently compressed
        compressed: Whether the artifact is currently compressed
    """

    artifact_id: str

    original_size: int

    algorithm: str = "GZIP"

    compressed_size: Optional[int] = None

    compressed: bool = True

    def __post_init__(self):
        self._require_text(self.artifact_id, "artifact ID")
        self._require_text(self.algorithm, "algorithm")

        if self.algorithm not in SUPPORTED_ALGORITHMS:
            raise ExecutionArtifactCompressionError(
                f"Unsupported compression algorithm {self.algorithm!r}: expected one of "
                f"{sorted(SUPPORTED_ALGORITHMS)}."
            )

        self._require_non_negative_int(self.original_size, "original_size")

        if not isinstance(self.compressed, bool):
            raise ExecutionArtifactCompressionError(
                "Cannot build an execution artifact compression record with a non-bool compressed."
            )

        if self.compressed_size is not None:
            self._require_non_negative_int(self.compressed_size, "compressed_size")

        if self.compressed and self.compressed_size is None:
            raise ExecutionArtifactCompressionError(
                "Cannot build a compressed execution artifact compression record without compressed_size."
            )

        if not self.compressed and self.compressed_size is not None:
            raise ExecutionArtifactCompressionError(
                "Cannot build a non-compressed execution artifact compression record with compressed_size set."
            )

        if self.compressed and self.compressed_size > self.original_size:
            raise ExecutionArtifactCompressionError(
                "Cannot build an execution artifact compression record whose compressed_size exceeds "
                "original_size."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionArtifactCompressionError(
                f"Cannot build an execution artifact compression record with an empty or blank {field_name}."
            )

    @staticmethod
    def _require_non_negative_int(value, field_name: str) -> None:
        if not isinstance(value, int) or isinstance(value, bool):
            raise ExecutionArtifactCompressionError(
                f"Cannot build an execution artifact compression record with a non-integer {field_name}."
            )

        if value < 0:
            raise ExecutionArtifactCompressionError(
                f"Cannot build an execution artifact compression record with a negative {field_name}."
            )
