from dataclasses import (
    dataclass,
    field,
)

from typing import Optional

from uuid import uuid4

from .execution_artifact_distribution_failover_error import (
    ExecutionArtifactDistributionFailoverError,
)

STATUS_REGISTERED = "REGISTERED"

STATUS_SUCCEEDED = "SUCCEEDED"

STATUS_FAILED = "FAILED"

STATUSES = (
    STATUS_REGISTERED,
    STATUS_SUCCEEDED,
    STATUS_FAILED,
)


@dataclass(frozen=True)
class ExecutionArtifactDistributionFailover:
    """
    Immutable snapshot of a version's failover configuration and its
    most recent execution outcome: which target was ultimately
    selected after preferring the primary target and skipping any
    failed targets.

    The failover is a value object only. It performs no distribution
    of its own; registering, executing, and querying failover is the
    responsibility of an execution artifact distribution failover
    service, which produces a new snapshot for every transition
    rather than mutating an existing one.

    Attributes:
        artifact_id: The identifier of the artifact whose version this
            failover configuration governs
        version_id: The identifier of the version this failover
            configuration governs
        primary_target: The target always attempted first
        backup_targets: The remaining targets, tried in this order
            only if primary_target fails
        status: REGISTERED before execute() has run, SUCCEEDED once a
            target has been selected, or FAILED if every target
            failed; one of STATUSES
        selected_target: The target execute() ultimately published to,
            or None if no execution has succeeded yet
        failover_id: The failover configuration's unique identifier
    """

    artifact_id: str

    version_id: str

    primary_target: str

    backup_targets: tuple

    status: str = STATUS_REGISTERED

    selected_target: Optional[str] = None

    failover_id: str = field(
        default_factory=lambda: str(uuid4()),
    )

    def __post_init__(self):
        self._require_text(self.failover_id, "failover ID")
        self._require_text(self.artifact_id, "artifact ID")
        self._require_text(self.version_id, "version ID")
        self._require_text(self.primary_target, "primary target")

        if not isinstance(self.backup_targets, tuple):
            raise ExecutionArtifactDistributionFailoverError(
                "Cannot build an execution artifact distribution failover with non-tuple "
                "backup_targets."
            )

        for backup_target in self.backup_targets:
            self._require_text(backup_target, "backup target")

        if self.status not in STATUSES:
            raise ExecutionArtifactDistributionFailoverError(
                f"Cannot build an execution artifact distribution failover with an unknown "
                f"status: {self.status!r}."
            )

        if self.status == STATUS_SUCCEEDED:
            self._require_text(self.selected_target, "selected target")

            if self.selected_target != self.primary_target and self.selected_target not in self.backup_targets:
                raise ExecutionArtifactDistributionFailoverError(
                    f"Cannot build a SUCCEEDED failover with selected_target "
                    f"{self.selected_target!r}: it is neither the primary nor a backup target."
                )
        elif self.selected_target is not None:
            raise ExecutionArtifactDistributionFailoverError(
                f"Cannot build a {self.status} failover with a non-None selected_target."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionArtifactDistributionFailoverError(
                f"Cannot build an execution artifact distribution failover with an empty or "
                f"blank {field_name}."
            )
