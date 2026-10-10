from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from .execution_runtime_health import (
    STATUSES as HEALTH_STATUSES,
)

from .execution_runtime_completion_error import (
    ExecutionRuntimeCompletionError,
)

FINAL_STATUS_SUCCEEDED = "SUCCEEDED"

FINAL_STATUS_FAILED = "FAILED"

FINAL_STATUSES = (
    FINAL_STATUS_SUCCEEDED,
    FINAL_STATUS_FAILED,
)


@dataclass(frozen=True)
class ExecutionRuntimeCompletion:
    """
    Immutable record of a runtime's final outcome, produced once
    lifecycle, health, resources, and shutdown have all completed,
    and never revised.

    The completion is a value object only. It performs no completion
    logic of its own; producing it from the runtime's finalized
    result, resource state, and health verdict is the responsibility
    of an execution runtime completion service.

    Attributes:
        completion_id: The completion's unique identifier
        runtime_id: The identifier of the runtime this completion
            describes
        final_status: The runtime's overall outcome, one of
            FINAL_STATUSES
        health_status: The resolved health verdict this completion
            was produced from
        output_ref: A reference to where the runtime's output was
            captured
        completed_at: When completion was produced
    """

    completion_id: str

    runtime_id: str

    final_status: str

    health_status: str

    output_ref: str

    completed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        self._require_text(self.completion_id, "completion ID")
        self._require_text(self.runtime_id, "runtime ID")
        self._require_text(self.output_ref, "output reference")

        if self.final_status not in FINAL_STATUSES:
            raise ExecutionRuntimeCompletionError(
                f"Cannot build an execution runtime completion with an unknown final_status: "
                f"{self.final_status!r}."
            )

        if self.health_status not in HEALTH_STATUSES:
            raise ExecutionRuntimeCompletionError(
                f"Cannot build an execution runtime completion with an unknown health_status: "
                f"{self.health_status!r}."
            )

        if self.completed_at is None or not isinstance(self.completed_at, datetime):
            raise ExecutionRuntimeCompletionError(
                "Cannot build an execution runtime completion with a non-datetime completed_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionRuntimeCompletionError(
                f"Cannot build an execution runtime completion with an empty or blank {field_name}."
            )
