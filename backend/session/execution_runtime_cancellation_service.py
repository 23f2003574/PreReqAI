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

from .execution_runtime_cancellation import (
    ExecutionRuntimeCancellation,
)

from .execution_runtime_cancellation_error import (
    ExecutionRuntimeCancellationError,
)

STATE_STOPPING = "STOPPING"

STATE_STOPPED = "STOPPED"

ACTIVE_STATES = ("RUNNING", "PAUSED")


class ExecutionRuntimeCancellationService:
    """
    Safely cancels an active runtime and propagates cancellation
    through its execution state.

    Composes with an existing runtime state service (anything
    exposing `state(runtime_id) -> object with .state` and
    `transition(runtime_id, state, reason)`, matching
    ExecutionRuntimeStateService), used as the single source of truth
    for whether a runtime is eligible to be cancelled, and to record
    the authoritative RUNNING/PAUSED -> STOPPING -> STOPPED
    transitions. A runtime driven to STOPPED this way is terminal, so
    an existing runtime pause/resume service will reject any later
    resume() against it on its own; this service does not need to
    call into one directly.

    Behavior:
    - request() admits a new cancellation record and drives the
      runtime to STOPPING, but only for a runtime whose current
      state is RUNNING or PAUSED
    - cancel() completes a runtime's requested cancellation by
      driving it from STOPPING to STOPPED and setting completed_at.
      Idempotent: cancelling an already-completed cancellation simply
      returns it unchanged
    - status() reports a runtime's current authoritative state
    - history() reports every cancellation requested for a runtime,
      in the order requested

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, state_service):
        self._state_service = state_service
        self._history_by_runtime = {}
        self._lock = RLock()

    def request(self, runtime_id: str, reason: str) -> ExecutionRuntimeCancellation:
        """
        Request cancellation of runtime_id.

        Raises:
            ExecutionRuntimeCancellationError: If runtime_id or
                reason is None or blank, runtime_id is unknown, or
                its current state is not RUNNING or PAUSED
        """

        self._validate_text(runtime_id, "runtime ID")
        self._validate_text(reason, "reason")

        current_state = self._current_state(runtime_id)

        if current_state not in ACTIVE_STATES:
            raise ExecutionRuntimeCancellationError(
                f"Cannot cancel runtime ID {runtime_id!r}: it is not active (state is {current_state!r})."
            )

        with self._lock:
            try:
                self._state_service.transition(runtime_id, STATE_STOPPING, reason)
            except Exception as error:
                raise ExecutionRuntimeCancellationError(
                    f"Cannot cancel runtime ID {runtime_id!r}."
                ) from error

            record = ExecutionRuntimeCancellation(
                cancellation_id=str(uuid4()),
                runtime_id=runtime_id,
                reason=reason,
                requested_at=datetime.now(timezone.utc),
                completed_at=None,
            )

            self._history_by_runtime.setdefault(runtime_id, []).append(record)

            return record

    def cancel(self, runtime_id: str) -> ExecutionRuntimeCancellation:
        """
        Complete runtime_id's requested cancellation. Idempotent:
        cancelling an already-completed cancellation simply returns
        it unchanged.

        Raises:
            ExecutionRuntimeCancellationError: If runtime_id is None
                or blank, or no cancellation has been requested for
                it
        """

        self._validate_text(runtime_id, "runtime ID")

        with self._lock:
            pending = self._latest(runtime_id)

            if pending is None:
                raise ExecutionRuntimeCancellationError(
                    f"Cannot cancel runtime ID {runtime_id!r}: no cancellation was requested for it."
                )

            if pending.completed_at is not None:
                return pending

            try:
                self._state_service.transition(runtime_id, STATE_STOPPED, pending.reason)
            except Exception as error:
                raise ExecutionRuntimeCancellationError(
                    f"Cannot cancel runtime ID {runtime_id!r}."
                ) from error

            completed = replace(pending, completed_at=datetime.now(timezone.utc))
            records = self._history_by_runtime[runtime_id]
            records[records.index(pending)] = completed

            return completed

    def status(self, runtime_id: str) -> str:
        """
        The current authoritative state of runtime_id.

        Raises:
            ExecutionRuntimeCancellationError: If runtime_id is None
                or blank, or runtime_id is unknown
        """

        self._validate_text(runtime_id, "runtime ID")

        return self._current_state(runtime_id)

    def history(self, runtime_id: str) -> tuple:
        """
        Every cancellation requested for runtime_id, oldest first.

        Raises:
            ExecutionRuntimeCancellationError: If runtime_id is None
                or blank, or no cancellation has been requested for
                it
        """

        self._validate_text(runtime_id, "runtime ID")

        with self._lock:
            records = self._history_by_runtime.get(runtime_id)

            if not records:
                raise ExecutionRuntimeCancellationError(
                    f"No cancellation is recorded for runtime ID {runtime_id!r}."
                )

            return tuple(records)

    def _current_state(self, runtime_id: str) -> str:
        try:
            return self._state_service.state(runtime_id).state
        except Exception as error:
            raise ExecutionRuntimeCancellationError(
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
            raise ExecutionRuntimeCancellationError(f"Cannot use an empty or blank {field_name}.")
