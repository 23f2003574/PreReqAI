from dataclasses import (
    dataclass,
)

from .execution_scheduler_failover_error import (
    ExecutionSchedulerFailoverError,
)

STATUS_ACTIVE = "ACTIVE"

STATUS_FAILED = "FAILED"

STATUSES = (
    STATUS_ACTIVE,
    STATUS_FAILED,
)


@dataclass(frozen=True)
class ExecutionSchedulerFailover:
    """
    Immutable record of which scheduler is currently responsible for
    a scope, chosen from a primary and an ordered list of backups.

    The record is a value object only. It performs no availability
    checking of its own; registering a scope's schedulers and
    (re)selecting among them is the responsibility of an execution
    scheduler failover service, which produces a new record for every
    update rather than mutating an existing one.

    Attributes:
        failover_id: The failover configuration's unique identifier
        scope_id: The scope this configuration governs
        primary_scheduler: The preferred scheduler for the scope
        backup_schedulers: The remaining schedulers, in the
            deterministic order they are tried after the primary
        selected_scheduler: The scheduler currently responsible for
            the scope, or None if every scheduler is unavailable
        status: The configuration's current state, one of STATUSES;
            FAILED exactly when selected_scheduler is None
    """

    failover_id: str

    scope_id: str

    primary_scheduler: str

    backup_schedulers: tuple

    selected_scheduler: str

    status: str = STATUS_ACTIVE

    def __post_init__(self):
        self._require_text(self.failover_id, "failover ID")
        self._require_text(self.scope_id, "scope ID")
        self._require_text(self.primary_scheduler, "primary scheduler")

        if self.backup_schedulers is None:
            raise ExecutionSchedulerFailoverError(
                "Cannot build an execution scheduler failover with a None backup_schedulers."
            )

        backups = list(self.backup_schedulers)

        for backup in backups:
            if not isinstance(backup, str) or not backup.strip():
                raise ExecutionSchedulerFailoverError(
                    "Cannot build an execution scheduler failover with a blank backup scheduler."
                )

        all_schedulers = [self.primary_scheduler] + backups

        if len(set(all_schedulers)) != len(all_schedulers):
            raise ExecutionSchedulerFailoverError(
                "Cannot build an execution scheduler failover with duplicate schedulers."
            )

        object.__setattr__(self, "backup_schedulers", tuple(backups))

        if self.status not in STATUSES:
            raise ExecutionSchedulerFailoverError(
                f"Cannot build an execution scheduler failover with an unknown status: {self.status!r}."
            )

        if self.status == STATUS_ACTIVE:
            if self.selected_scheduler is None or not self.selected_scheduler.strip():
                raise ExecutionSchedulerFailoverError(
                    "Cannot build an ACTIVE execution scheduler failover without a selected_scheduler."
                )

            if self.selected_scheduler not in all_schedulers:
                raise ExecutionSchedulerFailoverError(
                    f"Cannot build an execution scheduler failover: selected_scheduler "
                    f"{self.selected_scheduler!r} is not among its configured schedulers."
                )
        elif self.selected_scheduler is not None:
            raise ExecutionSchedulerFailoverError(
                "Cannot build a FAILED execution scheduler failover with a selected_scheduler set."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionSchedulerFailoverError(
                f"Cannot build an execution scheduler failover with an empty or blank {field_name}."
            )
