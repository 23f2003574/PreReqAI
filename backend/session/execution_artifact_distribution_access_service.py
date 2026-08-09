from threading import (
    RLock,
)

from .artifact_access_result import (
    ArtifactAccessResult,
)

from .artifact_distribution_permission import (
    SUPPORTED_OPERATIONS,
    ArtifactDistributionPermission,
)

from .execution_artifact_distribution_access_error import (
    ExecutionArtifactDistributionAccessError,
)


class ExecutionArtifactDistributionAccessService:
    """
    Controls which distribution channels may READ or PUBLISH
    artifacts of a given type, using an existing execution artifact
    distribution service to confirm a channel is genuinely known
    before permissions are granted for it.

    The service's responsibility is permission bookkeeping only. It
    does not enforce access anywhere itself; a caller is expected to
    call authorize() before routing or delivering to a channel and to
    act on its result.

    Behavior:
    - Default deny: authorize() disallows any channel/artifact type/
      operation combination that has not been explicitly granted
    - Granting an already granted channel/artifact type/operation is
      a no-op that returns the existing permission
    - revoke() takes effect immediately: the next authorize() call
      reflects it
    - Only READ and PUBLISH are supported operations

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, execution_artifact_distribution_service):
        """
        Args:
            execution_artifact_distribution_service: The service used
                to confirm a channel ID is known before a permission
                is granted for it. Any object exposing `channels()`,
                returning an iterable of objects with a `.channel_id`,
                is accepted
        """

        self._execution_artifact_distribution_service = execution_artifact_distribution_service
        self._permissions_by_id = {}
        self._permission_id_by_grant = {}
        self._permission_ids_by_channel = {}
        self._lock = RLock()

    def grant(
        self, channel_id: str, artifact_type: str, operation: str = "PUBLISH"
    ) -> ArtifactDistributionPermission:
        """
        Grant a channel permission to perform an operation against
        artifacts of a given type.

        Raises:
            ExecutionArtifactDistributionAccessError: If channel_id or
                artifact_type is None or blank, operation is not READ
                or PUBLISH, or the channel is not known to the
                execution artifact distribution service
        """

        self._validate_id(channel_id, "channel ID")
        self._validate_id(artifact_type, "artifact type")

        normalized_operation = self._normalize_operation(operation)

        with self._lock:
            self._ensure_channel_known(channel_id)

            key = (channel_id, artifact_type, normalized_operation)

            if key not in self._permission_id_by_grant:
                permission = ArtifactDistributionPermission(
                    channel_id=channel_id,
                    artifact_type=artifact_type,
                    operation=normalized_operation,
                )

                self._permissions_by_id[permission.permission_id] = permission
                self._permission_id_by_grant[key] = permission.permission_id
                self._permission_ids_by_channel.setdefault(channel_id, []).append(permission.permission_id)

            return self._permissions_by_id[self._permission_id_by_grant[key]]

    def revoke(self, permission_id: str) -> None:
        """
        Revoke a previously granted permission. A no-op if
        permission_id is not currently granted.

        Raises:
            ExecutionArtifactDistributionAccessError: If permission_id
                is None or blank
        """

        self._validate_id(permission_id, "permission ID")

        with self._lock:
            permission = self._permissions_by_id.pop(permission_id, None)

            if permission is None:
                return

            key = (permission.channel_id, permission.artifact_type, permission.operation)
            self._permission_id_by_grant.pop(key, None)
            self._permission_ids_by_channel[permission.channel_id].remove(permission_id)

    def authorize(self, channel_id: str, artifact_type: str, operation: str = "PUBLISH") -> ArtifactAccessResult:
        """
        Check whether a channel may perform an operation against
        artifacts of a given type, defaulting to deny when no
        matching grant exists.

        Raises:
            ExecutionArtifactDistributionAccessError: If channel_id or
                artifact_type is None or blank, operation is not READ
                or PUBLISH, or the channel is not known to the
                execution artifact distribution service
        """

        self._validate_id(channel_id, "channel ID")
        self._validate_id(artifact_type, "artifact type")

        normalized_operation = self._normalize_operation(operation)

        with self._lock:
            self._ensure_channel_known(channel_id)

            key = (channel_id, artifact_type, normalized_operation)

            if key in self._permission_id_by_grant:
                return ArtifactAccessResult(
                    allowed=True,
                    reason=f"Channel ID {channel_id!r} is granted {normalized_operation} on artifact type "
                    f"{artifact_type!r}.",
                )

            return ArtifactAccessResult(
                allowed=False,
                reason=f"Channel ID {channel_id!r} has no {normalized_operation} grant on artifact type "
                f"{artifact_type!r}: denied by default.",
            )

    def permissions(self, channel_id: str) -> list:
        """
        List every permission currently granted to a channel, in the
        order they were granted.

        Raises:
            ExecutionArtifactDistributionAccessError: If channel_id is
                None or blank, or the channel is not known to the
                execution artifact distribution service
        """

        self._validate_id(channel_id, "channel ID")

        with self._lock:
            self._ensure_channel_known(channel_id)

            return [
                self._permissions_by_id[permission_id]
                for permission_id in self._permission_ids_by_channel.get(channel_id, [])
            ]

    def _ensure_channel_known(self, channel_id: str) -> None:
        known_channel_ids = {
            channel.channel_id for channel in self._execution_artifact_distribution_service.channels()
        }

        if channel_id not in known_channel_ids:
            raise ExecutionArtifactDistributionAccessError(
                f"No distribution channel is known under channel ID {channel_id!r}."
            )

    @staticmethod
    def _normalize_operation(operation: str) -> str:
        if operation is None or not operation.strip():
            raise ExecutionArtifactDistributionAccessError("Cannot use an empty or blank operation.")

        normalized = operation.strip().upper()

        if normalized not in SUPPORTED_OPERATIONS:
            raise ExecutionArtifactDistributionAccessError(
                f"Unsupported operation {operation!r}: expected one of {sorted(SUPPORTED_OPERATIONS)}."
            )

        return normalized

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionArtifactDistributionAccessError(f"Cannot use an empty or blank {field_name}.")
