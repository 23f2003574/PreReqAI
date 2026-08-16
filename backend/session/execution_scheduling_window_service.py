from dataclasses import (
    replace,
)

from datetime import (
    datetime,
)

from threading import (
    RLock,
)

from uuid import uuid4

from .execution_scheduling_window import (
    ExecutionSchedulingWindow,
)

from .execution_scheduling_window_error import (
    ExecutionSchedulingWindowError,
)


class ExecutionSchedulingWindowService:
    """
    Defines the time windows during which queued jobs in a scope are
    eligible to start.

    Behavior:
    - create() admits a new, enabled window; starts_at must strictly
      precede ends_at
    - active() reports whether timestamp falls inside at least one
      enabled window for a scope; overlapping windows are handled
      transparently since any covering window is enough
    - next() reports the enabled window for a scope that is either
      covering timestamp or starts soonest after it, breaking ties on
      an identical starts_at by window_id, so the result is
      deterministic even when windows overlap
    - disable() takes a window out of effect for good

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self):
        self._windows_by_id = {}
        self._window_ids_by_scope = {}
        self._lock = RLock()

    def create(self, scope_id: str, starts_at: datetime, ends_at: datetime) -> ExecutionSchedulingWindow:
        """
        Create a new, enabled scheduling window for a scope.

        Raises:
            ExecutionSchedulingWindowError: If scope_id is None or
                blank, starts_at or ends_at is not a datetime, or
                starts_at does not strictly precede ends_at
        """

        self._validate_text(scope_id, "scope ID")

        with self._lock:
            window = ExecutionSchedulingWindow(
                window_id=str(uuid4()),
                scope_id=scope_id,
                starts_at=starts_at,
                ends_at=ends_at,
                enabled=True,
            )

            self._windows_by_id[window.window_id] = window
            self._window_ids_by_scope.setdefault(scope_id, []).append(window.window_id)

            return window

    def active(self, scope_id: str, timestamp: datetime) -> bool:
        """
        Whether timestamp falls inside at least one enabled window
        for scope_id.
        """

        self._validate_text(scope_id, "scope ID")

        with self._lock:
            return any(
                window.enabled and window.starts_at <= timestamp < window.ends_at
                for window in self._windows_for_scope(scope_id)
            )

    def next(self, scope_id: str, timestamp: datetime):
        """
        The enabled window for scope_id that is either covering
        timestamp or starts soonest after it.

        Returns:
            The window, or None if no enabled window covers or
            follows timestamp
        """

        self._validate_text(scope_id, "scope ID")

        with self._lock:
            candidates = [
                window
                for window in self._windows_for_scope(scope_id)
                if window.enabled and window.ends_at > timestamp
            ]

            if not candidates:
                return None

            candidates.sort(key=lambda window: (window.starts_at, window.window_id))

            return candidates[0]

    def disable(self, window_id: str) -> ExecutionSchedulingWindow:
        """
        Take a window out of effect for good.

        Raises:
            ExecutionSchedulingWindowError: If window_id is None or
                blank, no window is registered under it, or it is
                already disabled
        """

        self._validate_text(window_id, "window ID")

        with self._lock:
            window = self._resolve(window_id)

            if not window.enabled:
                raise ExecutionSchedulingWindowError(
                    f"Cannot disable window ID {window_id!r}: it is already disabled."
                )

            disabled = replace(window, enabled=False)
            self._windows_by_id[window_id] = disabled

            return disabled

    def _windows_for_scope(self, scope_id: str):
        return (self._windows_by_id[window_id] for window_id in self._window_ids_by_scope.get(scope_id, []))

    def _resolve(self, window_id: str) -> ExecutionSchedulingWindow:
        window = self._windows_by_id.get(window_id)

        if window is None:
            raise ExecutionSchedulingWindowError(f"No window is recorded under window ID {window_id!r}.")

        return window

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionSchedulingWindowError(f"Cannot use an empty or blank {field_name}.")
