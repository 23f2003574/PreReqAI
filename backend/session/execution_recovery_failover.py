from dataclasses import (
    dataclass,
    field,
)

from uuid import uuid4

from .execution_recovery_failover_error import (
    ExecutionRecoveryFailoverError,
)

SUPPORTED_STATUSES = frozenset(
    {
        "PENDING",
        "RESOLVED",
        "EXHAUSTED",
    }
)


@dataclass(frozen=True)
class ExecutionRecoveryFailover:
    """
    Immutable record of a session's failover from a primary recovery
    checkpoint to a backup, tried in priority order.

    The failover is a value object only. It performs no validation
    or selection of its own; registering a session's primary and
    backup checkpoints, executing the priority walk between them,
    and looking up the outcome is the responsibility of an execution
    recovery failover service.

    Attributes:
        failover_id: The failover's unique identifier
        session_id: The identifier of the execution session this
            failover is for
        primary_checkpoint_id: The checkpoint to try first
        backup_checkpoint_ids: The remaining checkpoints to try, in
            priority order, if the primary cannot be used
        selected_checkpoint: The checkpoint ID chosen to recover
            from, or None while PENDING or if every checkpoint was
            EXHAUSTED
        status: The failover's current status, one of PENDING,
            RESOLVED, or EXHAUSTED
    """

    session_id: str

    primary_checkpoint_id: str

    backup_checkpoint_ids: tuple = field(
        default_factory=tuple,
    )

    selected_checkpoint: str | None = None

    status: str = "PENDING"

    failover_id: str = field(
        default_factory=lambda: str(uuid4()),
    )

    def __post_init__(self):
        self._require_text(self.failover_id, "failover ID")
        self._require_text(self.session_id, "session ID")
        self._require_text(self.primary_checkpoint_id, "primary checkpoint ID")
        self._require_text(self.status, "status")

        if self.status not in SUPPORTED_STATUSES:
            raise ExecutionRecoveryFailoverError(
                f"Unsupported status {self.status!r}: expected one of {sorted(SUPPORTED_STATUSES)}."
            )

        if self.backup_checkpoint_ids is None:
            raise ExecutionRecoveryFailoverError(
                "Cannot build an execution recovery failover with a None backup_checkpoint_ids."
            )

        backup_list = list(self.backup_checkpoint_ids)

        for backup_checkpoint_id in backup_list:
            self._require_text(backup_checkpoint_id, "backup checkpoint ID")

        if len(set(backup_list)) != len(backup_list):
            raise ExecutionRecoveryFailoverError(
                "Cannot build an execution recovery failover with duplicate backup checkpoint IDs."
            )

        if self.primary_checkpoint_id in backup_list:
            raise ExecutionRecoveryFailoverError(
                "Cannot build an execution recovery failover with the primary checkpoint ID repeated as a backup."
            )

        object.__setattr__(self, "backup_checkpoint_ids", tuple(backup_list))

        candidate_ids = {self.primary_checkpoint_id, *backup_list}

        if self.status == "PENDING":
            if self.selected_checkpoint is not None:
                raise ExecutionRecoveryFailoverError(
                    "Cannot build an execution recovery failover that is PENDING with a selected_checkpoint set."
                )
        elif self.status == "RESOLVED":
            self._require_text(self.selected_checkpoint, "selected checkpoint")

            if self.selected_checkpoint not in candidate_ids:
                raise ExecutionRecoveryFailoverError(
                    f"Cannot build an execution recovery failover with selected_checkpoint "
                    f"{self.selected_checkpoint!r}: it is not among the primary or backup checkpoint IDs."
                )
        else:
            if self.selected_checkpoint is not None:
                raise ExecutionRecoveryFailoverError(
                    "Cannot build an execution recovery failover that is EXHAUSTED with a selected_checkpoint set."
                )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionRecoveryFailoverError(
                f"Cannot build an execution recovery failover with an empty or blank {field_name}."
            )
