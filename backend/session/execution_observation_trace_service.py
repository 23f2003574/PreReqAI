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

from .execution_observation_trace_error import (
    ExecutionObservationTraceError,
)

from .execution_observation_trace import (
    ExecutionObservationTrace,
    SUPPORTED_STATUSES,
)

TERMINAL_STATUSES = SUPPORTED_STATUSES - {"ACTIVE"}


class ExecutionObservationTraceService:
    """
    Tracks execution spans across a session's stages, end-to-end, for
    latency and failure diagnosis.

    The service's responsibility is trace bookkeeping only. It does
    not decide when a stage starts or finishes, or what its outcome
    is; a caller start()s and finish()es traces as stages run.
    Execution sessions and stages themselves are assumed to already
    exist and are never read or mutated by this service.

    Behavior:
    - start() rejects a session/stage pair that already has an
      ACTIVE trace; only one trace per session/stage may be active
      at a time
    - finish() is the only way a trace stops being ACTIVE; once
      finished, a trace is immutable and finish() rejects it
    - active() lists only a session's still-ACTIVE traces; history()
      lists every trace, active or finished, in chronological
      (started_at) order
    - duration() derives a finished trace's span directly from its
      started_at and finished_at timestamps
    - Every method rejects an unknown trace_id or session_id

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self):
        self._traces_by_id = {}
        self._trace_ids_by_session = {}
        self._active_trace_id_by_stage_key = {}
        self._lock = RLock()

    def start(self, session_id: str, stage_id: str) -> ExecutionObservationTrace:
        """
        Start a new ACTIVE trace for a session/stage.

        Raises:
            ExecutionObservationTraceError: If session_id or
                stage_id is None or blank, or the session/stage pair
                already has an ACTIVE trace
        """

        self._validate_id(session_id, "session ID")
        self._validate_id(stage_id, "stage ID")

        with self._lock:
            stage_key = (session_id, stage_id)

            if stage_key in self._active_trace_id_by_stage_key:
                raise ExecutionObservationTraceError(
                    f"Session ID {session_id!r} already has an active trace for stage ID {stage_id!r}."
                )

            trace = ExecutionObservationTrace(session_id=session_id, stage_id=stage_id)

            self._traces_by_id[trace.trace_id] = trace
            self._trace_ids_by_session.setdefault(session_id, []).append(trace.trace_id)
            self._active_trace_id_by_stage_key[stage_key] = trace.trace_id

            return trace

    def finish(self, trace_id: str, status: str) -> ExecutionObservationTrace:
        """
        Finish an ACTIVE trace, making it immutable.

        Raises:
            ExecutionObservationTraceError: If trace_id or status is
                None or blank, no trace is known under trace_id, it
                has already finished, or status is not a supported
                terminal status
        """

        self._validate_id(trace_id, "trace ID")
        self._validate_id(status, "status")

        with self._lock:
            trace = self._resolve(trace_id)

            if trace.status != "ACTIVE":
                raise ExecutionObservationTraceError(
                    f"Cannot finish trace ID {trace_id!r}: it is already {trace.status}."
                )

            if status not in TERMINAL_STATUSES:
                raise ExecutionObservationTraceError(
                    f"Unsupported terminal status {status!r}: expected one of {sorted(TERMINAL_STATUSES)}."
                )

            updated = replace(trace, status=status, finished_at=datetime.now(timezone.utc))
            self._traces_by_id[trace_id] = updated
            del self._active_trace_id_by_stage_key[(trace.session_id, trace.stage_id)]

            return updated

    def active(self, session_id: str) -> list:
        """
        List a session's still-ACTIVE traces, in the order they were
        started.

        Raises:
            ExecutionObservationTraceError: If session_id is None or
                blank
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            return [
                self._traces_by_id[trace_id]
                for trace_id in self._trace_ids_by_session.get(session_id, [])
                if self._traces_by_id[trace_id].status == "ACTIVE"
            ]

    def history(self, session_id: str) -> list:
        """
        List every trace recorded for a session, active or finished,
        oldest to newest.

        Raises:
            ExecutionObservationTraceError: If session_id is None or
                blank
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            traces = [self._traces_by_id[trace_id] for trace_id in self._trace_ids_by_session.get(session_id, [])]

            return sorted(traces, key=lambda trace: trace.started_at)

    def duration(self, trace_id: str) -> float:
        """
        Compute a finished trace's duration, in seconds, derived from
        its started_at and finished_at timestamps.

        Raises:
            ExecutionObservationTraceError: If trace_id is None or
                blank, no trace is known under it, or it has not yet
                finished
        """

        self._validate_id(trace_id, "trace ID")

        with self._lock:
            trace = self._resolve(trace_id)

            if trace.finished_at is None:
                raise ExecutionObservationTraceError(
                    f"Cannot compute duration for trace ID {trace_id!r}: it has not finished."
                )

            return (trace.finished_at - trace.started_at).total_seconds()

    def _resolve(self, trace_id: str) -> ExecutionObservationTrace:
        trace = self._traces_by_id.get(trace_id)

        if trace is None:
            raise ExecutionObservationTraceError(f"No trace is known under trace ID {trace_id!r}.")

        return trace

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionObservationTraceError(f"Cannot use an empty or blank {field_name}.")
