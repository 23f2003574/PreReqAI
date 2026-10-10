from dataclasses import (
    dataclass,
)

from .execution_storage_failover_error import (
    ExecutionStorageFailoverError,
)

STATUS_PRIMARY = "PRIMARY"

STATUS_FAILED_OVER = "FAILED_OVER"

STATUS_UNAVAILABLE = "UNAVAILABLE"

STATUSES = (
    STATUS_PRIMARY,
    STATUS_FAILED_OVER,
    STATUS_UNAVAILABLE,
)


@dataclass(frozen=True)
class ExecutionStorageFailover:
    """
    Immutable record of which target currently serves a volume's
    runtime storage access, chosen from a primary target and an
    ordered list of backup targets.

    The record is a value object only. It performs no availability or
    integrity checking of its own; registering a volume's targets and
    (re)selecting among them is the responsibility of an execution
    storage failover service, which produces a new record for every
    update rather than mutating an existing one.

    Attributes:
        failover_id: The failover configuration's unique identifier
        volume_id: The volume this configuration governs
        primary_target: The preferred target for the volume
        backup_targets: The remaining targets, in the deterministic
            order they are tried after the primary
        selected_target: The target currently serving the volume, or
            None if every target is unavailable or corrupt
        status: The configuration's current state, one of STATUSES;
            PRIMARY when selected_target is primary_target,
            FAILED_OVER when it is one of backup_targets, and
            UNAVAILABLE exactly when selected_target is None
    """

    failover_id: str

    volume_id: str

    primary_target: str

    backup_targets: tuple

    selected_target: str

    status: str

    def __post_init__(self):
        self._require_text(self.failover_id, "failover ID")
        self._require_text(self.volume_id, "volume ID")
        self._require_text(self.primary_target, "primary target")

        if self.backup_targets is None or not isinstance(self.backup_targets, tuple):
            raise ExecutionStorageFailoverError(
                "Cannot build an execution storage failover with a non-tuple backup_targets."
            )

        for backup in self.backup_targets:
            if not isinstance(backup, str) or not backup.strip():
                raise ExecutionStorageFailoverError(
                    "Cannot build an execution storage failover with a blank backup target."
                )

        all_targets = [self.primary_target] + list(self.backup_targets)

        if len(set(all_targets)) != len(all_targets):
            raise ExecutionStorageFailoverError(
                "Cannot build an execution storage failover with duplicate targets."
            )

        if self.status not in STATUSES:
            raise ExecutionStorageFailoverError(
                f"Cannot build an execution storage failover with an unknown status: {self.status!r}."
            )

        if self.status == STATUS_UNAVAILABLE:
            if self.selected_target is not None:
                raise ExecutionStorageFailoverError(
                    "Cannot build an UNAVAILABLE execution storage failover with a "
                    "selected_target set."
                )
        else:
            self._require_text(self.selected_target, "selected target")

            if self.status == STATUS_PRIMARY and self.selected_target != self.primary_target:
                raise ExecutionStorageFailoverError(
                    "Cannot build a PRIMARY execution storage failover whose selected_target "
                    "is not its primary target."
                )

            if self.status == STATUS_FAILED_OVER and self.selected_target not in self.backup_targets:
                raise ExecutionStorageFailoverError(
                    "Cannot build a FAILED_OVER execution storage failover whose selected_target "
                    "is not one of its backup targets."
                )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionStorageFailoverError(
                f"Cannot build an execution storage failover with an empty or blank {field_name}."
            )
