from dataclasses import (
    replace,
)

from threading import (
    RLock,
)

from .execution_artifact_encryption import (
    ExecutionArtifactEncryption,
)

from .execution_artifact_encryption_error import (
    ExecutionArtifactEncryptionError,
)


class ExecutionArtifactEncryptionService:
    """
    Encrypts registered execution artifacts and verifies their
    encryption state before distribution, using an existing execution
    artifact registry to confirm an artifact is genuinely known
    before it is encrypted.

    The service's responsibility is encryption bookkeeping only. It
    does not encrypt or decrypt artifact contents itself.

    Behavior:
    - An artifact may only be encrypted once it is registered
    - AES256 is the only supported algorithm
    - A missing or blank key ID is rejected
    - verify() is the gate a distribution flow calls before sending an
      artifact: it raises unless the artifact is currently encrypted,
      enforcing that distribution requires an encrypted artifact
    - decrypt() requires the artifact to be currently encrypted

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, execution_artifact_service):
        """
        Args:
            execution_artifact_service: The registry used to confirm
                an artifact ID is known before it is encrypted. Any
                object exposing `get(artifact_id)`, raising if the
                artifact is unknown, is accepted
        """

        self._execution_artifact_service = execution_artifact_service
        self._encryption_by_artifact = {}
        self._lock = RLock()

    def encrypt(self, artifact_id: str, key_id: str) -> ExecutionArtifactEncryption:
        """
        Encrypt a registered artifact under a key, using AES256.

        Raises:
            ExecutionArtifactEncryptionError: If artifact_id or
                key_id is None or blank, or the execution artifact
                registry does not recognize artifact_id
        """

        self._validate_id(artifact_id, "artifact ID")
        self._validate_id(key_id, "key ID")

        with self._lock:
            self._ensure_artifact_known(artifact_id)

            encryption = ExecutionArtifactEncryption(artifact_id=artifact_id, key_id=key_id)
            self._encryption_by_artifact[artifact_id] = encryption

            return encryption

    def verify(self, artifact_id: str) -> bool:
        """
        Confirm an artifact is currently encrypted, as required before
        it may be distributed under a policy that demands it.

        Raises:
            ExecutionArtifactEncryptionError: If artifact_id is None
                or blank, or the artifact is not currently encrypted
                (never encrypted, or since decrypted)
        """

        self._validate_id(artifact_id, "artifact ID")

        with self._lock:
            encryption = self._encryption_by_artifact.get(artifact_id)

            if encryption is None or not encryption.encrypted:
                raise ExecutionArtifactEncryptionError(
                    f"Cannot distribute artifact ID {artifact_id!r}: it is not currently encrypted."
                )

            return True

    def decrypt(self, artifact_id: str) -> ExecutionArtifactEncryption:
        """
        Decrypt a currently encrypted artifact.

        Raises:
            ExecutionArtifactEncryptionError: If artifact_id is None
                or blank, or the artifact is not currently encrypted
        """

        self._validate_id(artifact_id, "artifact ID")

        with self._lock:
            encryption = self._resolve(artifact_id)

            if not encryption.encrypted:
                raise ExecutionArtifactEncryptionError(
                    f"Cannot decrypt artifact ID {artifact_id!r}: it is not currently encrypted."
                )

            decrypted = replace(encryption, encrypted=False, encrypted_at=None)
            self._encryption_by_artifact[artifact_id] = decrypted

            return decrypted

    def status(self, artifact_id: str) -> ExecutionArtifactEncryption:
        """
        Look up an artifact's current encryption record.

        Raises:
            ExecutionArtifactEncryptionError: If artifact_id is None
                or blank, or no encryption has ever been recorded for
                it
        """

        self._validate_id(artifact_id, "artifact ID")

        with self._lock:
            return self._resolve(artifact_id)

    def _resolve(self, artifact_id: str) -> ExecutionArtifactEncryption:
        encryption = self._encryption_by_artifact.get(artifact_id)

        if encryption is None:
            raise ExecutionArtifactEncryptionError(
                f"No encryption has been recorded for artifact ID {artifact_id!r}."
            )

        return encryption

    def _ensure_artifact_known(self, artifact_id: str) -> None:
        try:
            self._execution_artifact_service.get(artifact_id)
        except Exception as error:
            raise ExecutionArtifactEncryptionError(
                f"No artifact is known under artifact ID {artifact_id!r}."
            ) from error

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionArtifactEncryptionError(f"Cannot use an empty or blank {field_name}.")
