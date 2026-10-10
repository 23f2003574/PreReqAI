from dataclasses import (
    dataclass,
)

from datetime import (
    datetime,
)

from .execution_runtime_finalization_error import (
    ExecutionRuntimeFinalizationError,
)

STATUS_COMPLETED = "COMPLETED"

STATUSES = (STATUS_COMPLETED,)


@dataclass(frozen=True)
class ExecutionRuntimeResult:
    """
    Immutable record of a runtime's final execution outcome, produced
    once and never revised.

    The result is a value object only. It performs no finalization
    logic of its own; producing it from a stopped runtime's lifecycle
    history is the responsibility of an execution runtime
    finalization service.

    Attributes:
        result_id: The result's unique identifier
        runtime_id: The identifier of the runtime this result
            describes
        status: The outcome's state, one of STATUSES
        output_ref: A reference to where the runtime's output was
            captured
        started_at: When the runtime started
        finished_at: When the runtime stopped
    """

    result_id: str

    runtime_id: str

    status: str

    output_ref: str

    started_at: datetime

    finished_at: datetime

    def __post_init__(self):
        self._require_text(self.result_id, "result ID")
        self._require_text(self.runtime_id, "runtime ID")
        self._require_text(self.output_ref, "output reference")

        if self.status not in STATUSES:
            raise ExecutionRuntimeFinalizationError(
                f"Cannot build an execution runtime result with an unknown status: {self.status!r}."
            )

        if self.started_at is None or not isinstance(self.started_at, datetime):
            raise ExecutionRuntimeFinalizationError(
                "Cannot build an execution runtime result with a non-datetime started_at."
            )

        if self.finished_at is None or not isinstance(self.finished_at, datetime):
            raise ExecutionRuntimeFinalizationError(
                "Cannot build an execution runtime result with a non-datetime finished_at."
            )

        if self.finished_at < self.started_at:
            raise ExecutionRuntimeFinalizationError(
                "Cannot build an execution runtime result with finished_at before started_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionRuntimeFinalizationError(
                f"Cannot build an execution runtime result with an empty or blank {field_name}."
            )
