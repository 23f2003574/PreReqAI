from dataclasses import (
    dataclass,
)

from numbers import (
    Integral,
)

from .execution_network_connection_limit_error import (
    ExecutionNetworkConnectionLimitError,
)


@dataclass(frozen=True)
class ExecutionNetworkConnectionLimit:
    """
    Immutable record of the maximum number of concurrent network
    connections a runtime may hold open.

    The limit is a value object only. It performs no accounting of
    its own; tracking acquired connections against this cap is the
    responsibility of an execution network connection limit service,
    which produces a new record for every reconfiguration rather than
    mutating an existing one.

    Attributes:
        limit_id: The limit's unique identifier
        runtime_id: The identifier of the runtime this limit governs
        max_connections: The maximum number of concurrent connections
            permitted
        enabled: Whether this limit is currently enforced
    """

    limit_id: str

    runtime_id: str

    max_connections: int

    enabled: bool = True

    def __post_init__(self):
        self._require_text(self.limit_id, "limit ID")
        self._require_text(self.runtime_id, "runtime ID")

        if (
            self.max_connections is None
            or isinstance(self.max_connections, bool)
            or not isinstance(self.max_connections, Integral)
            or self.max_connections < 1
        ):
            raise ExecutionNetworkConnectionLimitError(
                f"Cannot build an execution network connection limit with a max_connections below "
                f"1: {self.max_connections!r}."
            )

        if not isinstance(self.enabled, bool):
            raise ExecutionNetworkConnectionLimitError(
                f"Cannot build an execution network connection limit with a non-boolean enabled: "
                f"{self.enabled!r}."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionNetworkConnectionLimitError(
                f"Cannot build an execution network connection limit with an empty or blank {field_name}."
            )
