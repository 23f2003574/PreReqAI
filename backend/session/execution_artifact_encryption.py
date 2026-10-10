from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from typing import Optional

from .execution_artifact_encryption_error import (
    ExecutionArtifactEncryptionError,
)

SUPPORTED_ALGORITHMS = frozenset(
    {
        "AES256",
    }
)


@dataclass(frozen=True)
class ExecutionArtifactEncryption:
    """
    Immutable record of an execution artifact's current encryption
    state, used to verify it is encrypted before it may be
    distributed under a policy that demands it.

    The encryption record is a value object only. It performs no
    encryption of its own; encrypting, verifying, decrypting, and
    looking up an artifact's encryption state is the responsibility
    of an execution artifact encryption service.

    Attributes:
        artifact_id: The identifier of the execution artifact this
            record describes
        algorithm: The encryption algorithm used, currently always
            AES256
        key_id: The identifier of the key the artifact was encrypted
            with
        encrypted: Whether the artifact is currently encrypted
        encrypted_at: When the artifact was encrypted, or None if it
            is not currently encrypted
    """

    artifact_id: str

    key_id: str

    algorithm: str = "AES256"

    encrypted: bool = True

    encrypted_at: Optional[datetime] = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    def __post_init__(self):
        self._require_text(self.artifact_id, "artifact ID")
        self._require_text(self.key_id, "key ID")
        self._require_text(self.algorithm, "algorithm")

        if self.algorithm not in SUPPORTED_ALGORITHMS:
            raise ExecutionArtifactEncryptionError(
                f"Unsupported encryption algorithm {self.algorithm!r}: expected one of "
                f"{sorted(SUPPORTED_ALGORITHMS)}."
            )

        if not isinstance(self.encrypted, bool):
            raise ExecutionArtifactEncryptionError(
                "Cannot build an execution artifact encryption record with a non-bool encrypted."
            )

        if self.encrypted_at is not None and not isinstance(self.encrypted_at, datetime):
            raise ExecutionArtifactEncryptionError(
                "Cannot build an execution artifact encryption record with a non-datetime encrypted_at."
            )

        if self.encrypted and self.encrypted_at is None:
            raise ExecutionArtifactEncryptionError(
                "Cannot build an encrypted execution artifact encryption record without encrypted_at."
            )

        if not self.encrypted and self.encrypted_at is not None:
            raise ExecutionArtifactEncryptionError(
                "Cannot build a non-encrypted execution artifact encryption record with encrypted_at set."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionArtifactEncryptionError(
                f"Cannot build an execution artifact encryption record with an empty or blank {field_name}."
            )
