from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from typing import Any

from uuid import uuid4

from .execution_observation_trace_error import (
    ExecutionObservationTraceError,
)

SUPPORTED_STATUSES = frozenset(
    {
        "ACTIVE",
        "SUCCEEDED",
        "FAILED",
    }
)


@dataclass(frozen=True)
class ExecutionObservationTrace:
    """
    Immutable snapshot of an execution span, tracking a single stage
    of a session end-to-end for latency and failure diagnosis.

    The trace is a value object only. It performs no bookkeeping of
    its own; starting a trace, finishing it, and looking up active
    or historical traces is the responsibility of an execution
    observation trace service.

    Attributes:
        trace_id: The trace's unique identifier
        session_id: The identifier of the execution session the
            trace belongs to
        stage_id: The identifier of the stage this trace spans
        started_at: When this trace started
        finished_at: When this trace finished, or None while it is
            still ACTIVE
        status: The trace's current status, one of ACTIVE, SUCCEEDED,
            or FAILED
        metadata: Arbitrary additional details about the trace
    """

    session_id: str

    stage_id: str

    trace_id: str = field(
        default_factory=lambda: str(uuid4()),
    )

    started_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    finished_at: datetime | None = None

    status: str = "ACTIVE"

    metadata: dict[str, Any] = field(
        default_factory=dict,
    )

    def __post_init__(self):
        self._require_text(self.trace_id, "trace ID")
        self._require_text(self.session_id, "session ID")
        self._require_text(self.stage_id, "stage ID")
        self._require_text(self.status, "status")

        if self.status not in SUPPORTED_STATUSES:
            raise ExecutionObservationTraceError(
                f"Unsupported status {self.status!r}: expected one of {sorted(SUPPORTED_STATUSES)}."
            )

        if not isinstance(self.started_at, datetime):
            raise ExecutionObservationTraceError(
                "Cannot build an execution observation trace with a non-datetime started_at."
            )

        if self.status == "ACTIVE":
            if self.finished_at is not None:
                raise ExecutionObservationTraceError(
                    "Cannot build an execution observation trace that is ACTIVE with a finished_at set."
                )
        else:
            if not isinstance(self.finished_at, datetime):
                raise ExecutionObservationTraceError(
                    "Cannot build an execution observation trace with a non-ACTIVE status and a "
                    "non-datetime finished_at."
                )

            if self.finished_at < self.started_at:
                raise ExecutionObservationTraceError(
                    "Cannot build an execution observation trace with a finished_at before started_at."
                )

        if not isinstance(self.metadata, dict):
            raise ExecutionObservationTraceError(
                "Cannot build an execution observation trace with a non-dict metadata."
            )

        for key in self.metadata:
            self._require_text(key, "metadata key")

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionObservationTraceError(
                f"Cannot build an execution observation trace with an empty or blank {field_name}."
            )
