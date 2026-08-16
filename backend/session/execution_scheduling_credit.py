from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from numbers import (
    Real,
)

from .execution_fair_scheduling_error import (
    ExecutionFairSchedulingError,
)


@dataclass(frozen=True)
class ExecutionSchedulingCredit:
    """
    Immutable record of a job's standing in fair scheduling: how much
    weight it is owed and how much of that weight it has already
    consumed.

    The credit is a value object only. It performs no scheduling of
    its own; computing eligibility order and updating credit is the
    responsibility of an execution fair scheduling service, which
    produces a new record for every update rather than mutating an
    existing one.

    Attributes:
        job_id: The identifier of the job this credit belongs to
        weight: The job's scheduling weight, derived from its
            priority. Must be positive
        consumed: How much of the job's weight it has already used;
            higher consumed lowers its effective score, so heavy
            users of capacity yield to others of the same priority
        updated_at: When this credit was last touched
    """

    job_id: str

    weight: float

    consumed: float = 0.0

    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        self._require_text(self.job_id, "job ID")

        if not isinstance(self.weight, Real) or isinstance(self.weight, bool) or self.weight <= 0:
            raise ExecutionFairSchedulingError(
                "Cannot build an execution scheduling credit with a non-positive weight."
            )

        if not isinstance(self.consumed, Real) or isinstance(self.consumed, bool) or self.consumed < 0:
            raise ExecutionFairSchedulingError(
                "Cannot build an execution scheduling credit with a negative consumed."
            )

        if self.updated_at is None or not isinstance(self.updated_at, datetime):
            raise ExecutionFairSchedulingError(
                "Cannot build an execution scheduling credit with a non-datetime updated_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionFairSchedulingError(
                f"Cannot build an execution scheduling credit with an empty or blank {field_name}."
            )
