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

from .execution_runtime_pause import (
    ExecutionRuntimePause,
)

from .execution_runtime_pause_error import (
    ExecutionRuntimePauseError,
)

STATE_RUNNING = "RUNNING"

STATE_PAUSED = "PAUSED"

RESUME_REASON = "resumed"


class ExecutionRuntimePauseService:
    """
    Allows running executions to pause safely and resume from their
    preserved runtime state.

    Composes with an existing runtime state service (anything
    exposing `state(runtime_id) -> object with .state` and
    `transition(runtime_id, state, reason)`, matching
    ExecutionRuntimeStateService), used as the single source of truth
    for whether a runtime is eligible to pause or resume, and to
    record the authoritative RUNNING <-> PAUSED transition. This
    service layers its own pause history (reason, paused_at,
    resumed_at) on top of that authoritative state.

    Behavior:
    - pause() admits a new pause record, but only for a runtime whose
      current authoritative state is RUNNING; it also drives that
      state to PAUSED
    - resume() completes a runtime's active (unresumed) pause record
      by setting resumed_at, but only for a runtime whose current
      authoritative state is PAUSED; it also drives that state back
      to RUNNING
    - Both are rejected for a runtime in any other state, including a
      terminal one (STOPPED, FAILED), since neither RUNNING nor
      PAUSED can describe it
    - status() reports a runtime's current authoritative state
    - history() reports every pause a runtime has gone through, in
      the order it went through them

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, state_service):
        self._state_service = state_service
        self._history_by_runtime = {}
        self._lock = RLock()

    def pause(self, runtime_id: str, reason: str) -> ExecutionRuntimePause:
        """
        Pause runtime_id.

        Raises:
            ExecutionRuntimePauseError: If runtime_id or reason is
                None or blank, runtime_id is unknown, or its current
                state is not RUNNING
        """

        self._validate_text(runtime_id, "runtime ID")
        self._validate_text(reason, "reason")

        current_state = self._current_state(runtime_id)

        if current_state != STATE_RUNNING:
            raise ExecutionRuntimePauseError(
                f"Cannot pause runtime ID {runtime_id!r}: it is not running (state is {current_state!r})."
            )

        with self._lock:
            try:
                self._state_service.transition(runtime_id, STATE_PAUSED, reason)
            except Exception as error:
                raise ExecutionRuntimePauseError(
                    f"Cannot pause runtime ID {runtime_id!r}."
                ) from error

            record = ExecutionRuntimePause(
                pause_id=str(uuid4()),
                runtime_id=runtime_id,
                reason=reason,
                paused_at=datetime.now(timezone.utc),
                resumed_at=None,
            )

            self._history_by_runtime.setdefault(runtime_id, []).append(record)

            return record

    def resume(self, runtime_id: str) -> ExecutionRuntimePause:
        """
        Resume runtime_id from its active pause.

        Raises:
            ExecutionRuntimePauseError: If runtime_id is None or
                blank, runtime_id is unknown, its current state is
                not PAUSED, or it has no active pause recorded
        """

        self._validate_text(runtime_id, "runtime ID")

        current_state = self._current_state(runtime_id)

        if current_state != STATE_PAUSED:
            raise ExecutionRuntimePauseError(
                f"Cannot resume runtime ID {runtime_id!r}: it is not paused (state is {current_state!r})."
            )

        with self._lock:
            active = self._active_pause(runtime_id)

            if active is None:
                raise ExecutionRuntimePauseError(
                    f"Cannot resume runtime ID {runtime_id!r}: it has no active pause recorded."
                )

            try:
                self._state_service.transition(runtime_id, STATE_RUNNING, RESUME_REASON)
            except Exception as error:
                raise ExecutionRuntimePauseError(
                    f"Cannot resume runtime ID {runtime_id!r}."
                ) from error

            resumed = replace(active, resumed_at=datetime.now(timezone.utc))
            records = self._history_by_runtime[runtime_id]
            records[records.index(active)] = resumed

            return resumed

    def status(self, runtime_id: str) -> str:
        """
        The current authoritative state of runtime_id.

        Raises:
            ExecutionRuntimePauseError: If runtime_id is None or
                blank, or runtime_id is unknown
        """

        self._validate_text(runtime_id, "runtime ID")

        return self._current_state(runtime_id)

    def history(self, runtime_id: str) -> tuple:
        """
        Every pause runtime_id has gone through, oldest first.

        Raises:
            ExecutionRuntimePauseError: If runtime_id is None or
                blank, or no pause has been recorded for it
        """

        self._validate_text(runtime_id, "runtime ID")

        with self._lock:
            records = self._history_by_runtime.get(runtime_id)

            if not records:
                raise ExecutionRuntimePauseError(
                    f"No pause is recorded for runtime ID {runtime_id!r}."
                )

            return tuple(records)

    def _current_state(self, runtime_id: str) -> str:
        try:
            return self._state_service.state(runtime_id).state
        except Exception as error:
            raise ExecutionRuntimePauseError(
                f"Cannot resolve runtime ID {runtime_id!r}: it is unknown."
            ) from error

    def _active_pause(self, runtime_id: str):
        records = self._history_by_runtime.get(runtime_id, [])

        if records and records[-1].resumed_at is None:
            return records[-1]

        return None

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionRuntimePauseError(f"Cannot use an empty or blank {field_name}.")
