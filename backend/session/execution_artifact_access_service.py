from threading import (
    RLock,
)

from .artifact_access_result import (
    ArtifactAccessResult,
)

from .artifact_permission import (
    SUPPORTED_OPERATIONS,
    ArtifactPermission,
)

from .execution_artifact_access_error import (
    ExecutionArtifactAccessError,
)


class ExecutionArtifactAccessService:
    """
    Controls which principals may READ, PROMOTE, or DELETE execution
    artifacts already known to an execution artifact registry.

    The service's responsibility is permission bookkeeping only. It
    does not enforce access anywhere itself; a caller is expected to
    call authorize() before performing an operation and to act on its
    result.

    Behavior:
    - Default deny: authorize() disallows any principal/operation
      pair that has not been explicitly granted
    - A grant is made against an artifact_id and is inherited by
      every version of that artifact, since versions are never
      addressed independently of the artifact that owns them
    - revoke() takes effect immediately: the next authorize() call
      reflects it
    - Granting or revoking an already granted/revoked permission is a
      no-op

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, execution_artifact_service):
        """
        Args:
            execution_artifact_service: The registry used to confirm
                an artifact ID is known before permissions are
                granted, revoked, checked, or listed for it. Any
                object exposing `get(artifact_id)`, raising if the
                artifact is unknown, is accepted
        """

        self._execution_artifact_service = execution_artifact_service
        self._permissions_by_artifact = {}
        self._lock = RLock()

    def grant(self, artifact_id: str, principal: str, operation: str) -> ArtifactPermission:
        """
        Grant a principal permission to perform an operation against
        an artifact.

        Raises:
            ExecutionArtifactAccessError: If artifact_id, principal,
                or operation is None or blank, operation is not
                READ, PROMOTE, or DELETE, or the execution artifact
                registry does not recognize artifact_id
        """

        self._validate_id(artifact_id, "artifact ID")
        self._validate_id(principal, "principal")

        normalized_operation = self._normalize_operation(operation)

        with self._lock:
            self._ensure_artifact_known(artifact_id)

            permissions = self._permissions_by_artifact.setdefault(artifact_id, {})
            key = (principal, normalized_operation)

            if key not in permissions:
                permissions[key] = ArtifactPermission(
                    artifact_id=artifact_id,
                    principal=principal,
                    operation=normalized_operation,
                )

            return permissions[key]

    def revoke(self, artifact_id: str, principal: str, operation: str) -> None:
        """
        Revoke a principal's permission to perform an operation
        against an artifact, if granted. A no-op if it was not.

        Raises:
            ExecutionArtifactAccessError: If artifact_id, principal,
                or operation is None or blank, operation is not
                READ, PROMOTE, or DELETE, or the execution artifact
                registry does not recognize artifact_id
        """

        self._validate_id(artifact_id, "artifact ID")
        self._validate_id(principal, "principal")

        normalized_operation = self._normalize_operation(operation)

        with self._lock:
            self._ensure_artifact_known(artifact_id)

            permissions = self._permissions_by_artifact.get(artifact_id, {})
            permissions.pop((principal, normalized_operation), None)

    def authorize(self, artifact_id: str, principal: str, operation: str) -> ArtifactAccessResult:
        """
        Check whether a principal may perform an operation against an
        artifact, defaulting to deny when no matching grant exists.

        Raises:
            ExecutionArtifactAccessError: If artifact_id, principal,
                or operation is None or blank, operation is not
                READ, PROMOTE, or DELETE, or the execution artifact
                registry does not recognize artifact_id
        """

        self._validate_id(artifact_id, "artifact ID")
        self._validate_id(principal, "principal")

        normalized_operation = self._normalize_operation(operation)

        with self._lock:
            self._ensure_artifact_known(artifact_id)

            permissions = self._permissions_by_artifact.get(artifact_id, {})

            if (principal, normalized_operation) in permissions:
                return ArtifactAccessResult(
                    allowed=True,
                    reason=f"Principal {principal!r} is granted {normalized_operation} on artifact ID "
                    f"{artifact_id!r}.",
                )

            return ArtifactAccessResult(
                allowed=False,
                reason=f"Principal {principal!r} has no {normalized_operation} grant on artifact ID "
                f"{artifact_id!r}: denied by default.",
            )

    def permissions(self, artifact_id: str) -> list:
        """
        List every permission currently granted for an artifact, in
        the order they were granted.

        Raises:
            ExecutionArtifactAccessError: If artifact_id is None or
                blank, or the execution artifact registry does not
                recognize artifact_id
        """

        self._validate_id(artifact_id, "artifact ID")

        with self._lock:
            self._ensure_artifact_known(artifact_id)

            return list(self._permissions_by_artifact.get(artifact_id, {}).values())

    def _ensure_artifact_known(self, artifact_id: str) -> None:
        try:
            self._execution_artifact_service.get(artifact_id)
        except Exception as error:
            raise ExecutionArtifactAccessError(
                f"No artifact is known under artifact ID {artifact_id!r}."
            ) from error

    @staticmethod
    def _normalize_operation(operation: str) -> str:
        if operation is None or not operation.strip():
            raise ExecutionArtifactAccessError("Cannot use an empty or blank operation.")

        normalized = operation.strip().upper()

        if normalized not in SUPPORTED_OPERATIONS:
            raise ExecutionArtifactAccessError(
                f"Unsupported operation {operation!r}: expected one of {sorted(SUPPORTED_OPERATIONS)}."
            )

        return normalized

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionArtifactAccessError(f"Cannot use an empty or blank {field_name}.")
