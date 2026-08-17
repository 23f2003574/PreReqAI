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

from .execution_runtime import (
    ExecutionRuntime,
    STATUS_FAILED,
    STATUS_RUNNING,
)

from .execution_runtime_startup_error import (
    ExecutionRuntimeStartupError,
)

DISPATCH_STATUS_DISPATCHED = "DISPATCHED"


class ExecutionRuntimeStartupService:
    """
    Initializes a dispatched job into a running execution with
    explicit startup state.

    Composes with an existing runtime dispatch service (anything
    exposing `status(dispatch_id)` that returns an object with
    `.status` and `.target`, matching ExecutionRuntimeDispatch), used
    to confirm a dispatch is currently DISPATCHED, and to source the
    session the runtime starts within, before it can be started.

    Behavior:
    - start() admits a new RUNNING record, but only for a dispatch
      that is currently DISPATCHED, and only if its session does not
      already have an active runtime
    - fail() is idempotent: failing an already-FAILED runtime simply
      returns it unchanged. Startup failure is terminal; a FAILED
      runtime can never return to RUNNING
    - active() reports the currently active (RUNNING) runtimes for a
      given session

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, dispatch_service):
        self._dispatch_service = dispatch_service
        self._runtimes_by_id = {}
        self._lock = RLock()

    def start(self, dispatch_id: str) -> ExecutionRuntime:
        """
        Initialize dispatch_id into a running execution.

        Raises:
            ExecutionRuntimeStartupError: If dispatch_id is None or
                blank, dispatch_id is unknown, dispatch_id is not
                currently DISPATCHED, or its session already has an
                active runtime
        """

        self._validate_text(dispatch_id, "dispatch ID")

        try:
            dispatch = self._dispatch_service.status(dispatch_id)
        except Exception as error:
            raise ExecutionRuntimeStartupError(
                f"Cannot start dispatch ID {dispatch_id!r}: it is unknown."
            ) from error

        if dispatch.status != DISPATCH_STATUS_DISPATCHED:
            raise ExecutionRuntimeStartupError(
                f"Cannot start dispatch ID {dispatch_id!r}: it is not dispatched "
                f"(status is {dispatch.status!r})."
            )

        session_id = dispatch.target

        with self._lock:
            if self._active_for_session(session_id) is not None:
                raise ExecutionRuntimeStartupError(
                    f"Cannot start a runtime for session ID {session_id!r}: "
                    "it already has an active runtime."
                )

            runtime = ExecutionRuntime(
                runtime_id=str(uuid4()),
                dispatch_id=dispatch_id,
                session_id=session_id,
                status=STATUS_RUNNING,
                started_at=datetime.now(timezone.utc),
            )

            self._runtimes_by_id[runtime.runtime_id] = runtime

            return runtime

    def status(self, runtime_id: str) -> str:
        """
        The current status of a runtime.

        Raises:
            ExecutionRuntimeStartupError: If runtime_id is None or
                blank, or no runtime is registered under it
        """

        self._validate_text(runtime_id, "runtime ID")

        with self._lock:
            return self._resolve(runtime_id).status

    def active(self, session_id: str) -> tuple:
        """
        The currently active (RUNNING) runtimes for session_id.
        """

        self._validate_text(session_id, "session ID")

        with self._lock:
            return tuple(
                runtime
                for runtime in self._runtimes_by_id.values()
                if runtime.session_id == session_id and runtime.status == STATUS_RUNNING
            )

    def fail(self, runtime_id: str, reason: str) -> ExecutionRuntime:
        """
        Fail a runtime's startup. Idempotent: failing an
        already-FAILED runtime simply returns it unchanged.

        Raises:
            ExecutionRuntimeStartupError: If runtime_id or reason is
                None or blank, or no runtime is registered under
                runtime_id
        """

        self._validate_text(runtime_id, "runtime ID")
        self._validate_text(reason, "reason")

        with self._lock:
            runtime = self._resolve(runtime_id)

            if runtime.status == STATUS_FAILED:
                return runtime

            failed = replace(runtime, status=STATUS_FAILED)
            self._runtimes_by_id[runtime_id] = failed

            return failed

    def _active_for_session(self, session_id: str):
        for runtime in self._runtimes_by_id.values():
            if runtime.session_id == session_id and runtime.status == STATUS_RUNNING:
                return runtime

        return None

    def _resolve(self, runtime_id: str) -> ExecutionRuntime:
        runtime = self._runtimes_by_id.get(runtime_id)

        if runtime is None:
            raise ExecutionRuntimeStartupError(
                f"No runtime is recorded under runtime ID {runtime_id!r}."
            )

        return runtime

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionRuntimeStartupError(f"Cannot use an empty or blank {field_name}.")
