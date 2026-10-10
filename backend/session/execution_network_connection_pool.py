from dataclasses import (
    dataclass,
)

from numbers import (
    Integral,
)

from .execution_network_connection_pool_error import (
    ExecutionNetworkConnectionPoolError,
)


@dataclass(frozen=True)
class ExecutionNetworkConnectionPool:
    """
    Immutable snapshot of a runtime's pool of reusable, idle
    connections to one endpoint.

    The pool is a value object only. It performs no reuse or
    eviction logic of its own; acquiring, releasing, and evicting
    connections is the responsibility of an execution network
    connection pool service, which produces a new snapshot for every
    transition rather than mutating an existing one.

    Attributes:
        pool_id: The pool's unique identifier
        runtime_id: The identifier of the runtime this pool serves
        endpoint_id: The identifier of the endpoint this pool holds
            connections to
        max_idle: The maximum number of idle connections this pool
            may hold at once
        idle_connections: The connection IDs currently idle and
            available for reuse, at most max_idle of them
    """

    pool_id: str

    runtime_id: str

    endpoint_id: str

    max_idle: int

    idle_connections: tuple = ()

    def __post_init__(self):
        self._require_text(self.pool_id, "pool ID")
        self._require_text(self.runtime_id, "runtime ID")
        self._require_text(self.endpoint_id, "endpoint ID")

        if (
            self.max_idle is None
            or isinstance(self.max_idle, bool)
            or not isinstance(self.max_idle, Integral)
            or self.max_idle < 1
        ):
            raise ExecutionNetworkConnectionPoolError(
                f"Cannot build an execution network connection pool with a max_idle below 1: "
                f"{self.max_idle!r}."
            )

        if self.idle_connections is None or not isinstance(self.idle_connections, tuple):
            raise ExecutionNetworkConnectionPoolError(
                "Cannot build an execution network connection pool with a non-tuple idle_connections."
            )

        if len(self.idle_connections) > self.max_idle:
            raise ExecutionNetworkConnectionPoolError(
                f"Cannot build an execution network connection pool with {len(self.idle_connections)} "
                f"idle connections exceeding max_idle ({self.max_idle})."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionNetworkConnectionPoolError(
                f"Cannot build an execution network connection pool with an empty or blank {field_name}."
            )
