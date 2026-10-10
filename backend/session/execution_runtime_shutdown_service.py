from dataclasses import (
    replace,
)

from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from uuid import uuid4

from .execution_runtime_shutdown import (
    ExecutionRuntimeShutdown,
    STATUS_STOPPED,
    STATUS_STOPPING,
)

from .execution_runtime_shutdown_error import (
    ExecutionRuntimeShutdownError,
)

STATE_STOPPING = "STOPPING"

STATE_STOPPED = "STOPPED"

ACTIVE_STATES = ("RUNNING", "PAUSED")


class ExecutionRuntimeShutdownService:
    """
    Gracefully terminates a running runtime and releases its
    execution resources.

    Composes with:
    - an existing runtime state service (anything exposing
      `state(runtime_id) -> object with .state` and
      `transition(runtime_id, state, reason)`, matching
      ExecutionRuntimeStateService), used as the single source of
      truth for whether a runtime is eligible to shut down, and to
      record the authoritative RUNNING/PAUSED -> STOPPING -> STOPPED
      transitions
    - an existing resource manager (anything exposing
      `release(runtime_id)`), used to free the runtime's held
      execution resources once shutdown completes

    Behavior:
    - request() admits a new shutdown record and drives the runtime
      to STOPPING, but only for a runtime whose current state is
      RUNNING or PAUSED
    - shutdown() completes a runtime's requested shutdown by driving
      it from STOPPING to STOPPED, releasing its resources, and
      setting completed_at. Idempotent: shutting down an
      already-completed shutdown simply returns it unchanged, without
      releasing resources again
    - status() reports a runtime's current authoritative state
    - history() reports every shutdown requested for a runtime, in
      the order requested

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, state_service, resource_service):
        self._state_service = state_service
        self._resource_service = resource_service
        self._history_by_runtime = {}
        self._lock = RLock()

    def request(self, runtime_id: str, reason: str) -> ExecutionRuntimeShutdown:
        """
        Request a graceful shutdown of runtime_id.

        Raises:
            ExecutionRuntimeShutdownError: If runtime_id or reason is
                None or blank, runtime_id is unknown, or its current
                state is not RUNNING or PAUSED
        """

        self._validate_text(runtime_id, "runtime ID")
        self._validate_text(reason, "reason")

        current_state = self._current_state(runtime_id)

        if current_state not in ACTIVE_STATES:
            raise ExecutionRuntimeShutdownError(
                f"Cannot shut down runtime ID {runtime_id!r}: it is not active (state is {current_state!r})."
            )

        with self._lock:
            try:
                self._state_service.transition(runtime_id, STATE_STOPPING, reason)
            except Exception as error:
                raise ExecutionRuntimeShutdownError(
                    f"Cannot shut down runtime ID {runtime_id!r}."
                ) from error

            record = ExecutionRuntimeShutdown(
                shutdown_id=str(uuid4()),
                runtime_id=runtime_id,
                reason=reason,
                requested_at=datetime.now(timezone.utc),
                completed_at=None,
                status=STATUS_STOPPING,
            )

            self._history_by_runtime.setdefault(runtime_id, []).append(record)

            return record

    def shutdown(self, runtime_id: str) -> ExecutionRuntimeShutdown:
        """
        Complete runtime_id's requested shutdown, releasing its
        resources. Idempotent: shutting down an already-completed
        shutdown simply returns it unchanged.

        Raises:
            ExecutionRuntimeShutdownError: If runtime_id is None or
                blank, or no shutdown has been requested for it
        """

        self._validate_text(runtime_id, "runtime ID")

        with self._lock:
            pending = self._latest(runtime_id)

            if pending is None:
                raise ExecutionRuntimeShutdownError(
                    f"Cannot shut down runtime ID {runtime_id!r}: no shutdown was requested for it."
                )

            if pending.status == STATUS_STOPPED:
                return pending

            try:
                self._state_service.transition(runtime_id, STATE_STOPPED, pending.reason)
            except Exception as error:
                raise ExecutionRuntimeShutdownError(
                    f"Cannot shut down runtime ID {runtime_id!r}."
                ) from error

            try:
                self._resource_service.release(runtime_id)
            except Exception as error:
                raise ExecutionRuntimeShutdownError(
                    f"Cannot release resources for runtime ID {runtime_id!r}."
                ) from error

            completed = replace(
                pending,
                completed_at=datetime.now(timezone.utc),
                status=STATUS_STOPPED,
            )
            records = self._history_by_runtime[runtime_id]
            records[records.index(pending)] = completed

            return completed

    def status(self, runtime_id: str) -> str:
        """
        The current authoritative state of runtime_id.

        Raises:
            ExecutionRuntimeShutdownError: If runtime_id is None or
                blank, or runtime_id is unknown
        """

        self._validate_text(runtime_id, "runtime ID")

        return self._current_state(runtime_id)

    def history(self, runtime_id: str) -> tuple:
        """
        Every shutdown requested for runtime_id, oldest first.

        Raises:
            ExecutionRuntimeShutdownError: If runtime_id is None or
                blank, or no shutdown has been requested for it
        """

        self._validate_text(runtime_id, "runtime ID")

        with self._lock:
            records = self._history_by_runtime.get(runtime_id)

            if not records:
                raise ExecutionRuntimeShutdownError(
                    f"No shutdown is recorded for runtime ID {runtime_id!r}."
                )

            return tuple(records)

    def _current_state(self, runtime_id: str) -> str:
        try:
            return self._state_service.state(runtime_id).state
        except Exception as error:
            raise ExecutionRuntimeShutdownError(
                f"Cannot resolve runtime ID {runtime_id!r}: it is unknown."
            ) from error

    def _latest(self, runtime_id: str):
        records = self._history_by_runtime.get(runtime_id)

        if not records:
            return None

        return records[-1]

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionRuntimeShutdownError(f"Cannot use an empty or blank {field_name}.")
