from dataclasses import (
    replace,
)

from datetime import (
    datetime,
    timezone,
)

from numbers import (
    Real,
)

from threading import (
    RLock,
)

from uuid import uuid4

from .execution_runtime_timeout import (
    ExecutionRuntimeTimeout,
    STATUS_ARMED,
    STATUS_TRIGGERED,
)

from .execution_runtime_timeout_error import (
    ExecutionRuntimeTimeoutError,
)

STATE_FAILED = "FAILED"

TRIGGER_REASON = "execution timeout exceeded"

ACTIVE_STATES = ("RUNNING", "PAUSED")


class ExecutionRuntimeTimeoutService:
    """
    Detects runtimes that exceed their allowed execution duration and
    transitions them safely to failure.

    Composes with an existing runtime state service (anything
    exposing `state(runtime_id) -> object with .state` and
    `transition(runtime_id, state, reason)`, matching
    ExecutionRuntimeStateService), used as the single source of truth
    for whether a runtime is still eligible to time out, and to
    record the authoritative transition to FAILED. A runtime driven
    to FAILED this way is terminal, so an existing runtime
    pause/resume service will reject any later resume() against it on
    its own.

    Behavior:
    - configure() arms a new timeout for a runtime, starting its
      clock from now, but only for a runtime whose current state is
      RUNNING or PAUSED, and only with a positive limit_seconds
    - check() reports whether a configured runtime is still within
      its limit; an already-triggered runtime is never within limit
    - expired() reports every configured, still-ARMED runtime whose
      elapsed time has exceeded its limit
    - trigger() drives an expired runtime to FAILED. Idempotent:
      triggering an already-triggered timeout simply returns it
      unchanged

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, state_service):
        self._state_service = state_service
        self._timeouts_by_runtime = {}
        self._started_at_by_runtime = {}
        self._lock = RLock()

    def configure(self, runtime_id: str, limit_seconds: float) -> ExecutionRuntimeTimeout:
        """
        Arm a timeout for runtime_id, starting its clock from now.

        Raises:
            ExecutionRuntimeTimeoutError: If runtime_id is None or
                blank, limit_seconds is not a positive number,
                runtime_id is unknown, or its current state is not
                RUNNING or PAUSED
        """

        self._validate_text(runtime_id, "runtime ID")
        self._validate_limit(limit_seconds)

        current_state = self._current_state(runtime_id)

        if current_state not in ACTIVE_STATES:
            raise ExecutionRuntimeTimeoutError(
                f"Cannot configure a timeout for runtime ID {runtime_id!r}: "
                f"it is not active (state is {current_state!r})."
            )

        with self._lock:
            record = ExecutionRuntimeTimeout(
                timeout_id=str(uuid4()),
                runtime_id=runtime_id,
                limit_seconds=limit_seconds,
                triggered_at=None,
                status=STATUS_ARMED,
            )

            self._timeouts_by_runtime[runtime_id] = record
            self._started_at_by_runtime[runtime_id] = datetime.now(timezone.utc)

            return record

    def check(self, runtime_id: str) -> bool:
        """
        Whether runtime_id is still within its configured limit. An
        already-triggered timeout is never within limit.

        Raises:
            ExecutionRuntimeTimeoutError: If runtime_id is None or
                blank, or no timeout is configured for it
        """

        self._validate_text(runtime_id, "runtime ID")

        with self._lock:
            record = self._resolve(runtime_id)

            if record.status == STATUS_TRIGGERED:
                return False

            return self._elapsed(runtime_id) <= record.limit_seconds

    def expired(self) -> tuple:
        """
        The runtime IDs whose configured, still-ARMED timeout has
        exceeded its limit.
        """

        with self._lock:
            return tuple(
                runtime_id
                for runtime_id, record in self._timeouts_by_runtime.items()
                if record.status == STATUS_ARMED and self._elapsed(runtime_id) > record.limit_seconds
            )

    def trigger(self, runtime_id: str) -> ExecutionRuntimeTimeout:
        """
        Fire runtime_id's timeout, driving it to FAILED. Idempotent:
        triggering an already-triggered timeout simply returns it
        unchanged.

        Raises:
            ExecutionRuntimeTimeoutError: If runtime_id is None or
                blank, no timeout is configured for it, or its
                current state is not RUNNING or PAUSED
        """

        self._validate_text(runtime_id, "runtime ID")

        with self._lock:
            record = self._resolve(runtime_id)

            if record.status == STATUS_TRIGGERED:
                return record

            current_state = self._current_state(runtime_id)

            if current_state not in ACTIVE_STATES:
                raise ExecutionRuntimeTimeoutError(
                    f"Cannot trigger the timeout for runtime ID {runtime_id!r}: "
                    f"it is not active (state is {current_state!r})."
                )

            try:
                self._state_service.transition(runtime_id, STATE_FAILED, TRIGGER_REASON)
            except Exception as error:
                raise ExecutionRuntimeTimeoutError(
                    f"Cannot trigger the timeout for runtime ID {runtime_id!r}."
                ) from error

            triggered = replace(
                record,
                status=STATUS_TRIGGERED,
                triggered_at=datetime.now(timezone.utc),
            )
            self._timeouts_by_runtime[runtime_id] = triggered

            return triggered

    def _elapsed(self, runtime_id: str) -> float:
        started_at = self._started_at_by_runtime[runtime_id]
        return (datetime.now(timezone.utc) - started_at).total_seconds()

    def _resolve(self, runtime_id: str) -> ExecutionRuntimeTimeout:
        record = self._timeouts_by_runtime.get(runtime_id)

        if record is None:
            raise ExecutionRuntimeTimeoutError(
                f"No timeout is configured for runtime ID {runtime_id!r}."
            )

        return record

    def _current_state(self, runtime_id: str) -> str:
        try:
            return self._state_service.state(runtime_id).state
        except Exception as error:
            raise ExecutionRuntimeTimeoutError(
                f"Cannot resolve runtime ID {runtime_id!r}: it is unknown."
            ) from error

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionRuntimeTimeoutError(f"Cannot use an empty or blank {field_name}.")

    @staticmethod
    def _validate_limit(limit_seconds) -> None:
        if (
            limit_seconds is None
            or isinstance(limit_seconds, bool)
            or not isinstance(limit_seconds, Real)
            or limit_seconds <= 0
        ):
            raise ExecutionRuntimeTimeoutError(
                f"Cannot use a non-positive limit_seconds: {limit_seconds!r}."
            )
