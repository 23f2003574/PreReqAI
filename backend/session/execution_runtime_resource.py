from dataclasses import (
    dataclass,
)

from datetime import (
    datetime,
)

from numbers import (
    Real,
)

from .execution_runtime_resource_error import (
    ExecutionRuntimeResourceError,
)

STATUS_ALLOCATED = "ALLOCATED"

STATUS_RELEASED = "RELEASED"

STATUSES = (
    STATUS_ALLOCATED,
    STATUS_RELEASED,
)


@dataclass(frozen=True)
class ExecutionRuntimeResource:
    """
    Immutable record that a runtime holds (or held) a claim on some
    amount of a resource type.

    The resource is a value object only. It performs no allocation
    accounting of its own; allocating and releasing is the
    responsibility of an execution runtime resource service, which
    produces a new record for every transition rather than mutating
    an existing one.

    Attributes:
        resource_id: The resource claim's unique identifier
        runtime_id: The identifier of the runtime holding the claim
        resource_type: What kind of resource is claimed (for example,
            "gpu" or "memory")
        amount: How much of resource_type is claimed
        status: The claim's current state, one of STATUSES
        released_at: When the claim was released, or None if it is
            still held
    """

    resource_id: str

    runtime_id: str

    resource_type: str

    amount: float

    status: str = STATUS_ALLOCATED

    released_at: datetime = None

    def __post_init__(self):
        self._require_text(self.resource_id, "resource ID")
        self._require_text(self.runtime_id, "runtime ID")
        self._require_text(self.resource_type, "resource type")

        if (
            self.amount is None
            or isinstance(self.amount, bool)
            or not isinstance(self.amount, Real)
            or self.amount <= 0
        ):
            raise ExecutionRuntimeResourceError(
                f"Cannot build an execution runtime resource with a non-positive amount: {self.amount!r}."
            )

        if self.status not in STATUSES:
            raise ExecutionRuntimeResourceError(
                f"Cannot build an execution runtime resource with an unknown status: {self.status!r}."
            )

        if self.released_at is not None and not isinstance(self.released_at, datetime):
            raise ExecutionRuntimeResourceError(
                "Cannot build an execution runtime resource with a non-datetime released_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionRuntimeResourceError(
                f"Cannot build an execution runtime resource with an empty or blank {field_name}."
            )
