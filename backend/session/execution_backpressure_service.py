from dataclasses import (
    replace,
)

from threading import (
    RLock,
)

from .execution_backpressure_state import (
    ExecutionBackpressureState,
    STATUS_NORMAL,
    STATUS_SATURATED,
)

from .execution_backpressure_error import (
    ExecutionBackpressureError,
)


class ExecutionBackpressureService:
    """
    Prevents an overloaded execution scope from accepting unlimited
    queued work.

    Behavior:
    - configure() sets (or updates) the maximum queue depth allowed
      for a scope; re-configuring a scope updates its limit without
      disturbing work already recorded as queued in it
    - record_enqueue() raises a scope's queue depth by one, but only
      if it has spare capacity; record_dequeue() immediately lowers it
      by one, freeing capacity for the next enqueue
    - A scope's status is SATURATED exactly when its queue depth has
      reached its configured max_queue

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self):
        self._states_by_scope = {}
        self._lock = RLock()

    def configure(self, scope_id: str, max_queue: int) -> ExecutionBackpressureState:
        """
        Set or update the maximum queue depth allowed for a scope.

        Raises:
            ExecutionBackpressureError: If scope_id is None or blank,
                or max_queue is not an int of at least 1
        """

        self._validate_text(scope_id, "scope ID")

        with self._lock:
            existing = self._states_by_scope.get(scope_id)
            current_queue = existing.current_queue if existing is not None else 0

            if current_queue > max_queue:
                raise ExecutionBackpressureError(
                    f"Cannot configure scope ID {scope_id!r} with max_queue {max_queue!r}: it is below the "
                    f"{current_queue} jobs already queued."
                )

            state = ExecutionBackpressureState(
                scope_id=scope_id,
                max_queue=max_queue,
                current_queue=current_queue,
                status=STATUS_SATURATED if current_queue >= max_queue else STATUS_NORMAL,
            )

            self._states_by_scope[scope_id] = state

            return state

    def can_enqueue(self, scope_id: str) -> bool:
        """
        Whether the scope currently has spare queue capacity.

        Raises:
            ExecutionBackpressureError: If scope_id is None or blank,
                or no limit is configured for it
        """

        self._validate_text(scope_id, "scope ID")

        with self._lock:
            state = self._resolve(scope_id)

            return state.current_queue < state.max_queue

    def record_enqueue(self, scope_id: str) -> ExecutionBackpressureState:
        """
        Record that a job was accepted into a scope's queue.

        Raises:
            ExecutionBackpressureError: If scope_id is None or blank,
                no limit is configured for it, or its queue capacity
                is already reached
        """

        self._validate_text(scope_id, "scope ID")

        with self._lock:
            state = self._resolve(scope_id)

            if state.current_queue >= state.max_queue:
                raise ExecutionBackpressureError(
                    f"Cannot enqueue into scope ID {scope_id!r}: queue capacity is reached."
                )

            updated = self._with_queue(state, state.current_queue + 1)
            self._states_by_scope[scope_id] = updated

            return updated

    def record_dequeue(self, scope_id: str) -> ExecutionBackpressureState:
        """
        Record that a job left a scope's queue, immediately freeing
        one unit of capacity.

        Raises:
            ExecutionBackpressureError: If scope_id is None or blank,
                no limit is configured for it, or its queue is already
                empty
        """

        self._validate_text(scope_id, "scope ID")

        with self._lock:
            state = self._resolve(scope_id)

            if state.current_queue <= 0:
                raise ExecutionBackpressureError(
                    f"Cannot dequeue from scope ID {scope_id!r}: its queue is already empty."
                )

            updated = self._with_queue(state, state.current_queue - 1)
            self._states_by_scope[scope_id] = updated

            return updated

    def status(self, scope_id: str) -> str:
        """
        The current backpressure status of a scope.

        Raises:
            ExecutionBackpressureError: If scope_id is None or blank,
                or no limit is configured for it
        """

        self._validate_text(scope_id, "scope ID")

        with self._lock:
            return self._resolve(scope_id).status

    @staticmethod
    def _with_queue(state: ExecutionBackpressureState, current_queue: int) -> ExecutionBackpressureState:
        return replace(
            state,
            current_queue=current_queue,
            status=STATUS_SATURATED if current_queue >= state.max_queue else STATUS_NORMAL,
        )

    def _resolve(self, scope_id: str) -> ExecutionBackpressureState:
        state = self._states_by_scope.get(scope_id)

        if state is None:
            raise ExecutionBackpressureError(f"No backpressure limit is configured for scope ID {scope_id!r}.")

        return state

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionBackpressureError(f"Cannot use an empty or blank {field_name}.")
