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

from .execution_runtime import (
    STATUS_RUNNING,
)

from .execution_runtime_heartbeat import (
    ExecutionRuntimeHeartbeat,
    STATUS_OK,
)

from .execution_runtime_heartbeat_error import (
    ExecutionRuntimeHeartbeatError,
)

DEFAULT_STALE_TIMEOUT_SECONDS = 30


class ExecutionRuntimeHeartbeatService:
    """
    Tracks runtime liveness and detects executions that stop
    responding.

    Composes with an existing runtime startup service (anything
    exposing `status(runtime_id) -> str`, matching
    ExecutionRuntimeStartupService), used to confirm a runtime is
    currently RUNNING before it can heartbeat. This service never
    calls back into the startup service to change a runtime's state;
    it only observes and reports liveness.

    Behavior:
    - record() admits a new heartbeat, but only for a runtime that is
      currently RUNNING, and keeps it as that runtime's latest
    - last() reports a runtime's latest recorded heartbeat, or None
      if it has never heartbeated
    - healthy() reports whether a runtime's latest heartbeat is within
      timeout seconds of now; a runtime that has never heartbeated is
      never healthy
    - stale() sweeps every runtime this service has ever recorded a
      heartbeat for and reports those whose latest heartbeat is older
      than stale_timeout_seconds (missing or expired)

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, startup_service, stale_timeout_seconds: float = DEFAULT_STALE_TIMEOUT_SECONDS):
        self._startup_service = startup_service
        self._stale_timeout_seconds = stale_timeout_seconds
        self._latest_by_runtime = {}
        self._lock = RLock()

    def record(self, runtime_id: str) -> ExecutionRuntimeHeartbeat:
        """
        Record a liveness signal for runtime_id.

        Raises:
            ExecutionRuntimeHeartbeatError: If runtime_id is None or
                blank, runtime_id is unknown, or runtime_id is not
                currently RUNNING
        """

        self._validate_text(runtime_id, "runtime ID")

        try:
            status = self._startup_service.status(runtime_id)
        except Exception as error:
            raise ExecutionRuntimeHeartbeatError(
                f"Cannot record a heartbeat for runtime ID {runtime_id!r}: it is unknown."
            ) from error

        if status != STATUS_RUNNING:
            raise ExecutionRuntimeHeartbeatError(
                f"Cannot record a heartbeat for runtime ID {runtime_id!r}: "
                f"it is not running (status is {status!r})."
            )

        with self._lock:
            heartbeat = ExecutionRuntimeHeartbeat(
                heartbeat_id=str(uuid4()),
                runtime_id=runtime_id,
                recorded_at=datetime.now(timezone.utc),
                status=STATUS_OK,
            )

            self._latest_by_runtime[runtime_id] = heartbeat

            return heartbeat

    def last(self, runtime_id: str):
        """
        The latest heartbeat recorded for runtime_id, or None if it
        has never heartbeated.
        """

        self._validate_text(runtime_id, "runtime ID")

        with self._lock:
            return self._latest_by_runtime.get(runtime_id)

    def healthy(self, runtime_id: str, timeout: float) -> bool:
        """
        Whether runtime_id's latest heartbeat is within timeout
        seconds of now. A runtime that has never heartbeated is
        never healthy.
        """

        self._validate_text(runtime_id, "runtime ID")
        self._validate_timeout(timeout)

        with self._lock:
            heartbeat = self._latest_by_runtime.get(runtime_id)

            if heartbeat is None:
                return False

            age = (datetime.now(timezone.utc) - heartbeat.recorded_at).total_seconds()

            return age <= timeout

    def stale(self) -> tuple:
        """
        The runtime IDs whose latest heartbeat is missing or has
        expired (older than stale_timeout_seconds).
        """

        with self._lock:
            now = datetime.now(timezone.utc)

            return tuple(
                runtime_id
                for runtime_id, heartbeat in self._latest_by_runtime.items()
                if (now - heartbeat.recorded_at).total_seconds() > self._stale_timeout_seconds
            )

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionRuntimeHeartbeatError(f"Cannot use an empty or blank {field_name}.")

    @staticmethod
    def _validate_timeout(timeout) -> None:
        if timeout is None or isinstance(timeout, bool) or not isinstance(timeout, Real):
            raise ExecutionRuntimeHeartbeatError(f"Cannot use a non-numeric timeout: {timeout!r}.")
