from dataclasses import (
    replace,
)

from threading import (
    RLock,
)

from uuid import uuid4

from .execution_network_connection_pool import (
    ExecutionNetworkConnectionPool,
)

from .execution_network_connection_pool_error import (
    ExecutionNetworkConnectionPoolError,
)


class ExecutionNetworkConnectionPoolService:
    """
    Reuses established network connections to reduce connection setup
    overhead.

    Composes with:
        health_service: healthy(endpoint_id) -> bool
            (ExecutionNetworkEndpointHealthService)

    Behavior:
    - configure() replaces a runtime/endpoint pair's pool with a
      fresh, empty one, discarding anything previously idle or
      checked out under it
    - acquire() reuses a healthy idle connection when one is
      available; when the endpoint is currently unhealthy, every idle
      connection is discarded first (never reused), and a new
      connection is created instead
    - release() returns a checked-out connection to its pool's idle
      set, but never lets that set exceed max_idle: a connection
      released past capacity is discarded rather than kept
    - evict() discards every idle connection held by a runtime/
      endpoint pair without disturbing what is currently checked out
    - stats() reports a pool's current idle and checked-out counts

    Each pool is isolated per (runtime_id, endpoint_id) pair.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, health_service):
        self._health_service = health_service
        self._pools_by_key = {}
        self._checked_out = {}
        self._lock = RLock()

    def configure(self, runtime_id: str, endpoint_id: str, max_idle: int) -> ExecutionNetworkConnectionPool:
        """
        Replace the pool for (runtime_id, endpoint_id) with a fresh,
        empty one.

        Raises:
            ExecutionNetworkConnectionPoolError: If runtime_id or
                endpoint_id is None or blank, or max_idle is not an
                integer >= 1
        """

        self._validate_text(runtime_id, "runtime ID")
        self._validate_text(endpoint_id, "endpoint ID")

        pool = ExecutionNetworkConnectionPool(
            pool_id=str(uuid4()),
            runtime_id=runtime_id,
            endpoint_id=endpoint_id,
            max_idle=max_idle,
            idle_connections=(),
        )

        key = (runtime_id, endpoint_id)

        with self._lock:
            self._pools_by_key[key] = pool

            for connection_id in [cid for cid, k in self._checked_out.items() if k == key]:
                del self._checked_out[connection_id]

        return pool

    def acquire(self, runtime_id: str, endpoint_id: str) -> str:
        """
        Acquire a connection for (runtime_id, endpoint_id), reusing a
        healthy idle one first and creating a new one otherwise.

        Raises:
            ExecutionNetworkConnectionPoolError: If runtime_id or
                endpoint_id is None or blank, or no pool is
                configured for the pair
        """

        self._validate_text(runtime_id, "runtime ID")
        self._validate_text(endpoint_id, "endpoint ID")

        key = (runtime_id, endpoint_id)

        with self._lock:
            pool = self._resolve_pool(key)

            idle_connections = pool.idle_connections if self._is_healthy(endpoint_id) else ()

            if idle_connections:
                connection_id = idle_connections[0]
                remaining = idle_connections[1:]
            else:
                connection_id = str(uuid4())
                remaining = ()

            self._pools_by_key[key] = replace(pool, idle_connections=remaining)
            self._checked_out[connection_id] = key

            return connection_id

    def release(self, connection_id: str) -> ExecutionNetworkConnectionPool:
        """
        Return a checked-out connection to its pool's idle set,
        discarding it instead if the pool is already at max_idle.

        Raises:
            ExecutionNetworkConnectionPoolError: If connection_id is
                None or blank, or it is not currently checked out
        """

        self._validate_text(connection_id, "connection ID")

        with self._lock:
            key = self._checked_out.get(connection_id)

            if key is None:
                raise ExecutionNetworkConnectionPoolError(
                    f"Cannot release connection ID {connection_id!r}: it is not checked out."
                )

            del self._checked_out[connection_id]

            pool = self._resolve_pool(key)

            if len(pool.idle_connections) < pool.max_idle:
                pool = replace(pool, idle_connections=pool.idle_connections + (connection_id,))

            self._pools_by_key[key] = pool

            return pool

    def evict(self, runtime_id: str, endpoint_id: str) -> ExecutionNetworkConnectionPool:
        """
        Discard every idle connection held by (runtime_id,
        endpoint_id), leaving checked-out connections untouched.

        Raises:
            ExecutionNetworkConnectionPoolError: If runtime_id or
                endpoint_id is None or blank, or no pool is
                configured for the pair
        """

        self._validate_text(runtime_id, "runtime ID")
        self._validate_text(endpoint_id, "endpoint ID")

        key = (runtime_id, endpoint_id)

        with self._lock:
            pool = self._resolve_pool(key)
            evicted = replace(pool, idle_connections=())
            self._pools_by_key[key] = evicted

            return evicted

    def stats(self, runtime_id: str, endpoint_id: str) -> dict:
        """
        A dict with idle, checked_out, and max_idle counts for
        (runtime_id, endpoint_id).

        Raises:
            ExecutionNetworkConnectionPoolError: If runtime_id or
                endpoint_id is None or blank, or no pool is
                configured for the pair
        """

        self._validate_text(runtime_id, "runtime ID")
        self._validate_text(endpoint_id, "endpoint ID")

        key = (runtime_id, endpoint_id)

        with self._lock:
            pool = self._resolve_pool(key)
            checked_out = sum(1 for k in self._checked_out.values() if k == key)

            return {
                "idle": len(pool.idle_connections),
                "checked_out": checked_out,
                "max_idle": pool.max_idle,
            }

    def _resolve_pool(self, key) -> ExecutionNetworkConnectionPool:
        pool = self._pools_by_key.get(key)

        if pool is None:
            raise ExecutionNetworkConnectionPoolError(
                f"No connection pool is configured for runtime ID {key[0]!r} and endpoint ID "
                f"{key[1]!r}."
            )

        return pool

    def _is_healthy(self, endpoint_id: str) -> bool:
        try:
            return bool(self._health_service.healthy(endpoint_id))
        except Exception:
            return False

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionNetworkConnectionPoolError(f"Cannot use an empty or blank {field_name}.")
