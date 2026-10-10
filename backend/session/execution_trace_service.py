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

from .execution_trace import (
    ExecutionTrace,
    STATUS_ACTIVE,
    TERMINAL_STATUSES,
)

from .execution_trace_error import (
    ExecutionTraceError,
)


class ExecutionTraceService:
    """
    Tracks a complete execution operation as a tree of nested spans
    across a runtime's stages.

    Composes with an existing runtime service (anything exposing
    `status(runtime_id) -> str`, matching
    ExecutionRuntimeStartupService), used to confirm a runtime exists
    before a trace can be started within it.

    Behavior:
    - start() admits a new ACTIVE trace; if parent_span_id is given,
      it must reference a trace already recorded by this service
    - finish() transitions a trace to a terminal status (COMPLETED,
      FAILED, or CANCELLED), but only for a trace that is currently
      ACTIVE; once finished, a trace's record never changes again
    - active() reports a runtime's currently-ACTIVE traces
    - children() reports every trace started with a given trace_id as
      its parent_span_id
    - history() reports every trace started for a runtime, oldest to
      newest

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, runtime_service):
        self._runtime_service = runtime_service
        self._traces_by_id = {}
        self._lock = RLock()

    def start(self, runtime_id: str, operation: str, parent_span_id: str = None) -> ExecutionTrace:
        """
        Start a new ACTIVE trace for runtime_id.

        Raises:
            ExecutionTraceError: If runtime_id or operation is None
                or blank, runtime_id is unknown, or parent_span_id is
                given but does not reference a known trace
        """

        self._validate_text(runtime_id, "runtime ID")
        self._validate_text(operation, "operation")
        self._confirm_runtime_exists(runtime_id)

        with self._lock:
            if parent_span_id is not None:
                self._validate_text(parent_span_id, "parent span ID")

                if parent_span_id not in self._traces_by_id:
                    raise ExecutionTraceError(
                        f"Cannot start a trace with parent span ID {parent_span_id!r}: it is unknown."
                    )

            trace = ExecutionTrace(
                trace_id=str(uuid4()),
                runtime_id=runtime_id,
                operation=operation,
                parent_span_id=parent_span_id,
                started_at=datetime.now(timezone.utc),
                finished_at=None,
                status=STATUS_ACTIVE,
            )

            self._traces_by_id[trace.trace_id] = trace

            return trace

    def finish(self, trace_id: str, status: str) -> ExecutionTrace:
        """
        Finish an ACTIVE trace with a terminal status.

        Raises:
            ExecutionTraceError: If trace_id is None or blank, status
                is not one of TERMINAL_STATUSES, no trace is
                registered under trace_id, or it is not currently
                ACTIVE
        """

        self._validate_text(trace_id, "trace ID")

        if status not in TERMINAL_STATUSES:
            raise ExecutionTraceError(
                f"Cannot finish a trace with an unknown status: {status!r}."
            )

        with self._lock:
            trace = self._resolve(trace_id)

            if trace.status != STATUS_ACTIVE:
                raise ExecutionTraceError(
                    f"Cannot finish trace ID {trace_id!r}: it is not active (status is {trace.status!r})."
                )

            finished = replace(
                trace,
                status=status,
                finished_at=datetime.now(timezone.utc),
            )
            self._traces_by_id[trace_id] = finished

            return finished

    def active(self, runtime_id: str) -> tuple:
        """
        runtime_id's currently-ACTIVE traces, oldest to newest.

        Raises:
            ExecutionTraceError: If runtime_id is None or blank
        """

        self._validate_text(runtime_id, "runtime ID")

        with self._lock:
            matching = [
                trace
                for trace in self._traces_by_id.values()
                if trace.runtime_id == runtime_id and trace.status == STATUS_ACTIVE
            ]

        return tuple(sorted(matching, key=lambda trace: trace.started_at))

    def children(self, trace_id: str) -> tuple:
        """
        Every trace started with trace_id as its parent_span_id,
        oldest to newest.

        Raises:
            ExecutionTraceError: If trace_id is None or blank, or no
                trace is registered under trace_id
        """

        self._validate_text(trace_id, "trace ID")

        with self._lock:
            self._resolve(trace_id)

            matching = [
                trace
                for trace in self._traces_by_id.values()
                if trace.parent_span_id == trace_id
            ]

        return tuple(sorted(matching, key=lambda trace: trace.started_at))

    def history(self, runtime_id: str) -> tuple:
        """
        Every trace started for runtime_id, oldest to newest.

        Raises:
            ExecutionTraceError: If runtime_id is None or blank
        """

        self._validate_text(runtime_id, "runtime ID")

        with self._lock:
            matching = [
                trace
                for trace in self._traces_by_id.values()
                if trace.runtime_id == runtime_id
            ]

        return tuple(sorted(matching, key=lambda trace: trace.started_at))

    def _resolve(self, trace_id: str) -> ExecutionTrace:
        trace = self._traces_by_id.get(trace_id)

        if trace is None:
            raise ExecutionTraceError(
                f"No trace is recorded under trace ID {trace_id!r}."
            )

        return trace

    def _confirm_runtime_exists(self, runtime_id: str) -> None:
        try:
            self._runtime_service.status(runtime_id)
        except Exception as error:
            raise ExecutionTraceError(
                f"Cannot start a trace for runtime ID {runtime_id!r}: it is unknown."
            ) from error

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionTraceError(f"Cannot use an empty or blank {field_name}.")
