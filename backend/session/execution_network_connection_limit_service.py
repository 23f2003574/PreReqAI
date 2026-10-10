from threading import (
    RLock,
)

from uuid import uuid4

from .execution_network_connection_limit import (
    ExecutionNetworkConnectionLimit,
)

from .execution_network_connection_limit_error import (
    ExecutionNetworkConnectionLimitError,
)


class ExecutionNetworkConnectionLimitService:
    """
    Prevents a runtime from opening excessive concurrent network
    connections.

    Behavior:
    - configure() replaces a runtime's limit with a freshly built one
      and atomically clears any connections held under the previous
      configuration
    - can_open() reports whether one more connection may currently be
      acquired; a disabled limit always reports True
    - acquire() admits connection_id into a runtime's held set, but
      only once per connection_id, and only while capacity remains
      for an enabled limit
    - release() is idempotent: releasing a connection_id that is not
      currently held simply does nothing, immediately freeing its
      slot when it was held
    - active() reports the connection IDs currently held by a runtime

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self):
        self._limits_by_runtime = {}
        self._held_by_runtime = {}
        self._lock = RLock()

    def configure(
        self, runtime_id: str, max_connections: int, enabled: bool = True
    ) -> ExecutionNetworkConnectionLimit:
        """
        Replace runtime_id's connection limit with max_connections.
        A disabled limit (enabled=False) is tracked but never
        enforced by can_open() or acquire().

        Raises:
            ExecutionNetworkConnectionLimitError: If runtime_id is
                None or blank, or max_connections is not an integer
                >= 1
        """

        self._validate_text(runtime_id, "runtime ID")

        limit = ExecutionNetworkConnectionLimit(
            limit_id=str(uuid4()),
            runtime_id=runtime_id,
            max_connections=max_connections,
            enabled=enabled,
        )

        with self._lock:
            self._limits_by_runtime[runtime_id] = limit
            self._held_by_runtime[runtime_id] = set()

        return limit

    def can_open(self, runtime_id: str) -> bool:
        """
        Whether runtime_id currently has capacity to open one more
        connection. Always True for a disabled limit.

        Raises:
            ExecutionNetworkConnectionLimitError: If runtime_id is
                None or blank, or no limit is configured for it
        """

        self._validate_text(runtime_id, "runtime ID")

        limit = self._resolve_limit(runtime_id)

        if not limit.enabled:
            return True

        with self._lock:
            return len(self._held_by_runtime.get(runtime_id, ())) < limit.max_connections

    def acquire(self, runtime_id: str, connection_id: str) -> None:
        """
        Count connection_id against runtime_id's limit.

        Raises:
            ExecutionNetworkConnectionLimitError: If runtime_id or
                connection_id is None or blank, no limit is
                configured for runtime_id, connection_id is already
                held by runtime_id, or an enabled limit has no
                remaining capacity
        """

        self._validate_text(runtime_id, "runtime ID")
        self._validate_text(connection_id, "connection ID")

        limit = self._resolve_limit(runtime_id)

        with self._lock:
            held = self._held_by_runtime.setdefault(runtime_id, set())

            if connection_id in held:
                raise ExecutionNetworkConnectionLimitError(
                    f"Cannot acquire connection ID {connection_id!r} for runtime ID {runtime_id!r}: "
                    f"it is already counted."
                )

            if limit.enabled and len(held) >= limit.max_connections:
                raise ExecutionNetworkConnectionLimitError(
                    f"Cannot acquire connection ID {connection_id!r} for runtime ID {runtime_id!r}: "
                    f"it is at capacity ({limit.max_connections})."
                )

            held.add(connection_id)

    def release(self, runtime_id: str, connection_id: str) -> None:
        """
        Stop counting connection_id against runtime_id's limit,
        immediately freeing its slot. Idempotent: releasing a
        connection_id that is not currently held does nothing.

        Raises:
            ExecutionNetworkConnectionLimitError: If runtime_id or
                connection_id is None or blank, or no limit is
                configured for runtime_id
        """

        self._validate_text(runtime_id, "runtime ID")
        self._validate_text(connection_id, "connection ID")

        self._resolve_limit(runtime_id)

        with self._lock:
            self._held_by_runtime.get(runtime_id, set()).discard(connection_id)

    def active(self, runtime_id: str) -> tuple:
        """
        The connection IDs currently held by runtime_id.

        Raises:
            ExecutionNetworkConnectionLimitError: If runtime_id is
                None or blank, or no limit is configured for it
        """

        self._validate_text(runtime_id, "runtime ID")

        self._resolve_limit(runtime_id)

        with self._lock:
            return tuple(self._held_by_runtime.get(runtime_id, ()))

    def _resolve_limit(self, runtime_id: str) -> ExecutionNetworkConnectionLimit:
        limit = self._limits_by_runtime.get(runtime_id)

        if limit is None:
            raise ExecutionNetworkConnectionLimitError(
                f"No connection limit is configured for runtime ID {runtime_id!r}."
            )

        return limit

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionNetworkConnectionLimitError(f"Cannot use an empty or blank {field_name}.")
