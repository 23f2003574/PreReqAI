import hashlib

from threading import (
    RLock,
)

from .execution_artifact_signature import (
    ExecutionArtifactSignature,
)

from .execution_artifact_signing_error import (
    ExecutionArtifactSigningError,
)


class ExecutionArtifactSigningService:
    """
    Signs registered execution artifacts so consumers can verify
    publisher authenticity before distribution, using an existing
    execution artifact registry to confirm an artifact is genuinely
    known before it is signed.

    The service's responsibility is signature bookkeeping only. It
    does not read artifact contents itself: a signature is computed
    deterministically, using SHA256, from the artifact ID and key ID
    it was signed under.

    Behavior:
    - An artifact may only be signed once it is registered
    - An artifact may have at most one recorded signature; sign()
      rejects an artifact that is already signed
    - A missing or blank key ID is rejected
    - verify() is read-only: it never records, overwrites, or
      otherwise mutates an artifact's recorded signature, and never
      raises for a mismatched signature, only for one that was never
      recorded, letting distribution treat "unsigned" and "wrongly
      signed" as distinct failure modes

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, execution_artifact_service):
        """
        Args:
            execution_artifact_service: The registry used to confirm
                an artifact ID is known before it is signed. Any
                object exposing `get(artifact_id)`, raising if the
                artifact is unknown, is accepted
        """

        self._execution_artifact_service = execution_artifact_service
        self._signature_by_artifact = {}
        self._lock = RLock()

    def sign(self, artifact_id: str, key_id: str) -> ExecutionArtifactSignature:
        """
        Sign a registered artifact under a key, using SHA256-based
        signing.

        Raises:
            ExecutionArtifactSigningError: If artifact_id or key_id
                is None or blank, the execution artifact registry
                does not recognize artifact_id, or the artifact
                already has a recorded signature
        """

        self._validate_id(artifact_id, "artifact ID")
        self._validate_id(key_id, "key ID")

        with self._lock:
            self._ensure_artifact_known(artifact_id)

            if artifact_id in self._signature_by_artifact:
                raise ExecutionArtifactSigningError(
                    f"Artifact ID {artifact_id!r} already has a recorded signature."
                )

            signature = ExecutionArtifactSignature(
                artifact_id=artifact_id,
                key_id=key_id,
                signature=self._compute_signature(artifact_id, key_id),
            )

            self._signature_by_artifact[artifact_id] = signature

            return signature

    def verify(self, artifact_id: str, signature: str) -> bool:
        """
        Compare a candidate signature against an artifact's recorded
        signature. Read-only: never mutates recorded state.

        Raises:
            ExecutionArtifactSigningError: If artifact_id or
                signature is None or blank, or the artifact has no
                recorded signature
        """

        self._validate_id(artifact_id, "artifact ID")
        self._validate_id(signature, "signature")

        with self._lock:
            recorded = self._resolve(artifact_id)

            return recorded.signature == signature

    def status(self, artifact_id: str) -> ExecutionArtifactSignature:
        """
        Look up an artifact's recorded signature.

        Raises:
            ExecutionArtifactSigningError: If artifact_id is None or
                blank, or the artifact has no recorded signature
        """

        self._validate_id(artifact_id, "artifact ID")

        with self._lock:
            return self._resolve(artifact_id)

    @staticmethod
    def _compute_signature(artifact_id: str, key_id: str) -> str:
        canonical = f"{artifact_id}:{key_id}"

        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _resolve(self, artifact_id: str) -> ExecutionArtifactSignature:
        signature = self._signature_by_artifact.get(artifact_id)

        if signature is None:
            raise ExecutionArtifactSigningError(
                f"No signature is recorded for artifact ID {artifact_id!r}."
            )

        return signature

    def _ensure_artifact_known(self, artifact_id: str) -> None:
        try:
            self._execution_artifact_service.get(artifact_id)
        except Exception as error:
            raise ExecutionArtifactSigningError(
                f"No artifact is known under artifact ID {artifact_id!r}."
            ) from error

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionArtifactSigningError(f"Cannot use an empty or blank {field_name}.")
