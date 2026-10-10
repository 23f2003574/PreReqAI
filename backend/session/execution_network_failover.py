from dataclasses import (
    dataclass,
)

from .execution_network_failover_error import (
    ExecutionNetworkFailoverError,
)

STATUS_PRIMARY = "PRIMARY"

STATUS_FAILOVER = "FAILOVER"

STATUS_FAILED = "FAILED"

STATUSES = (
    STATUS_PRIMARY,
    STATUS_FAILOVER,
    STATUS_FAILED,
)


@dataclass(frozen=True)
class ExecutionNetworkFailover:
    """
    Immutable snapshot of which of a runtime's endpoints is currently
    selected to carry its traffic.

    The failover is a value object only. It performs no selection
    logic of its own; deciding whether to use the primary endpoint or
    fail over to a backup is the responsibility of an execution
    network failover service, which produces a new snapshot for every
    selection rather than mutating an existing one.

    Attributes:
        failover_id: The snapshot's unique identifier
        runtime_id: The identifier of the runtime this failover
            serves
        primary_endpoint: The endpoint preferred above all others
        backup_endpoints: The endpoints tried, in order, if the
            primary is unavailable
        selected_endpoint: The endpoint currently chosen to carry
            traffic, or None when every endpoint is unavailable
        status: The outcome of the selection, one of STATUSES
    """

    failover_id: str

    runtime_id: str

    primary_endpoint: str

    backup_endpoints: tuple

    selected_endpoint: str

    status: str

    def __post_init__(self):
        self._require_text(self.failover_id, "failover ID")
        self._require_text(self.runtime_id, "runtime ID")
        self._require_text(self.primary_endpoint, "primary endpoint")

        if self.backup_endpoints is None or not isinstance(self.backup_endpoints, tuple):
            raise ExecutionNetworkFailoverError(
                "Cannot build an execution network failover with a non-tuple backup_endpoints."
            )

        for backup in self.backup_endpoints:
            self._require_text(backup, "backup endpoint")

        if self.status not in STATUSES:
            raise ExecutionNetworkFailoverError(
                f"Cannot build an execution network failover with an unknown status: {self.status!r}."
            )

        if self.status == STATUS_FAILED:
            if self.selected_endpoint is not None:
                raise ExecutionNetworkFailoverError(
                    "Cannot build an execution network failover with a selected_endpoint while FAILED."
                )
        else:
            self._require_text(self.selected_endpoint, "selected endpoint")

            eligible = (self.primary_endpoint,) + self.backup_endpoints

            if self.selected_endpoint not in eligible:
                raise ExecutionNetworkFailoverError(
                    f"Cannot build an execution network failover with a selected_endpoint "
                    f"{self.selected_endpoint!r} that is neither the primary nor a backup."
                )

            if self.status == STATUS_PRIMARY and self.selected_endpoint != self.primary_endpoint:
                raise ExecutionNetworkFailoverError(
                    "Cannot build an execution network failover with status PRIMARY when "
                    "selected_endpoint is not the primary endpoint."
                )

            if self.status == STATUS_FAILOVER and self.selected_endpoint == self.primary_endpoint:
                raise ExecutionNetworkFailoverError(
                    "Cannot build an execution network failover with status FAILOVER when "
                    "selected_endpoint is the primary endpoint."
                )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionNetworkFailoverError(
                f"Cannot build an execution network failover with an empty or blank {field_name}."
            )
