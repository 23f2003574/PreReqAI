from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from uuid import uuid4

from .execution_artifact_signing_error import (
    ExecutionArtifactSigningError,
)

SUPPORTED_ALGORITHMS = frozenset(
    {
        "SHA256",
    }
)


@dataclass(frozen=True)
class ExecutionArtifactSignature:
    """
    Immutable record of a signature computed over a registered
    execution artifact, letting a consumer verify its publisher's
    authenticity before distribution.

    The signature is a value object only. It performs no signing of
    its own; signing, verifying, and looking up an artifact's
    signature is the responsibility of an execution artifact signing
    service.

    Attributes:
        artifact_id: The identifier of the execution artifact this
            signature covers
        key_id: The identifier of the key the artifact was signed
            with
        signature: The computed signature value
        algorithm: The signing algorithm used, currently always
            SHA256-based
        signature_id: The signature's unique identifier
        signed_at: When this signature was computed
    """

    artifact_id: str

    key_id: str

    signature: str

    algorithm: str = "SHA256"

    signature_id: str = field(
        default_factory=lambda: str(uuid4()),
    )

    signed_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    def __post_init__(self):
        self._require_text(self.artifact_id, "artifact ID")
        self._require_text(self.key_id, "key ID")
        self._require_text(self.signature, "signature")
        self._require_text(self.algorithm, "algorithm")
        self._require_text(self.signature_id, "signature ID")

        if self.algorithm not in SUPPORTED_ALGORITHMS:
            raise ExecutionArtifactSigningError(
                f"Unsupported signing algorithm {self.algorithm!r}: expected one of {sorted(SUPPORTED_ALGORITHMS)}."
            )

        if not isinstance(self.signed_at, datetime):
            raise ExecutionArtifactSigningError(
                "Cannot build an execution artifact signature with a non-datetime signed_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionArtifactSigningError(
                f"Cannot build an execution artifact signature with an empty or blank {field_name}."
            )
