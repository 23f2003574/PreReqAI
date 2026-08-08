from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from .execution_artifact_integrity_error import (
    ExecutionArtifactIntegrityError,
)

SUPPORTED_ALGORITHMS = frozenset(
    {
        "SHA256",
        "SHA512",
    }
)


@dataclass(frozen=True)
class ExecutionArtifactIntegrity:
    """
    Immutable content checksum baseline for a single execution
    artifact version, used to detect corruption or unexpected
    modification.

    The integrity record is a value object only. It performs no
    verification of its own; recording and verifying checksums is
    the responsibility of an execution artifact integrity service.

    Attributes:
        version_id: The identifier of the execution artifact version
            this checksum belongs to
        checksum: The recorded checksum of the version's contents
        algorithm: The hashing algorithm used to compute checksum,
            one of SHA256 or SHA512
        verified_at: When this checksum was recorded as the trusted
            baseline for the version
    """

    version_id: str

    checksum: str

    algorithm: str

    verified_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    def __post_init__(self):
        self._require_text(self.version_id, "version ID")
        self._require_text(self.checksum, "checksum")
        self._require_text(self.algorithm, "algorithm")

        if self.algorithm not in SUPPORTED_ALGORITHMS:
            raise ExecutionArtifactIntegrityError(
                f"Unsupported checksum algorithm {self.algorithm!r}: expected one of "
                f"{sorted(SUPPORTED_ALGORITHMS)}."
            )

        if not isinstance(self.verified_at, datetime):
            raise ExecutionArtifactIntegrityError(
                "Cannot build an execution artifact integrity record with a non-datetime verified_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionArtifactIntegrityError(
                f"Cannot build an execution artifact integrity record with an empty or blank {field_name}."
            )
