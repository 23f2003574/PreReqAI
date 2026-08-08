from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from .execution_artifact_bundle_integrity_error import (
    ExecutionArtifactBundleIntegrityError,
)

SUPPORTED_ALGORITHMS = frozenset(
    {
        "SHA256",
        "SHA512",
    }
)


@dataclass(frozen=True)
class ArtifactBundleIntegrity:
    """
    Immutable checksum baseline for a bundle's complete, ordered set
    of version IDs, used to detect a bundle whose version set has
    drifted from what was originally recorded.

    The integrity record is a value object only. It performs no
    verification of its own; recording and verifying bundle checksums
    is the responsibility of an execution artifact bundle integrity
    service.

    Attributes:
        bundle_id: The identifier of the bundle this checksum
            belongs to
        checksum: The recorded checksum, covering the bundle's
            ordered version IDs
        algorithm: The hashing algorithm used to compute checksum,
            one of SHA256 or SHA512
        verified_at: When this checksum was recorded as the trusted
            baseline for the bundle
    """

    bundle_id: str

    checksum: str

    algorithm: str

    verified_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    def __post_init__(self):
        self._require_text(self.bundle_id, "bundle ID")
        self._require_text(self.checksum, "checksum")
        self._require_text(self.algorithm, "algorithm")

        if self.algorithm not in SUPPORTED_ALGORITHMS:
            raise ExecutionArtifactBundleIntegrityError(
                f"Unsupported checksum algorithm {self.algorithm!r}: expected one of "
                f"{sorted(SUPPORTED_ALGORITHMS)}."
            )

        if not isinstance(self.verified_at, datetime):
            raise ExecutionArtifactBundleIntegrityError(
                "Cannot build a bundle integrity record with a non-datetime verified_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionArtifactBundleIntegrityError(
                f"Cannot build a bundle integrity record with an empty or blank {field_name}."
            )
