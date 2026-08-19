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

from .execution_storage_tier import (
    TIERS,
)

from .execution_storage_cost_profile_error import (
    ExecutionStorageCostProfileError,
)


@dataclass(frozen=True)
class ExecutionStorageCostProfile:
    """
    Immutable snapshot of a resource's estimated storage cost and its
    recommended tier placement, as of a single calculation.

    The profile is a value object only. It performs no estimation or
    recommendation of its own; calculating cost, recommending a tier,
    and applying that recommendation is the responsibility of an
    execution storage cost service, which produces a new snapshot for
    every calculation rather than mutating an existing one.

    Attributes:
        resource_id: The identifier of the resource this profile
            describes
        current_tier: The resource's tier as of this calculation, one
            of TIERS
        estimated_cost: The estimated cost of storing the resource at
            current_tier; never negative
        recommended_tier: The tier recommended for the resource, one
            of TIERS; equal to current_tier when no change is
            currently safe or beneficial
        calculated_at: When this profile was calculated
    """

    resource_id: str

    current_tier: str

    estimated_cost: float

    recommended_tier: str

    calculated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        self._require_text(self.resource_id, "resource ID")

        if self.current_tier not in TIERS:
            raise ExecutionStorageCostProfileError(
                f"Cannot build an execution storage cost profile with an unknown current_tier: "
                f"{self.current_tier!r}."
            )

        if self.recommended_tier not in TIERS:
            raise ExecutionStorageCostProfileError(
                f"Cannot build an execution storage cost profile with an unknown "
                f"recommended_tier: {self.recommended_tier!r}."
            )

        if (
            self.estimated_cost is None
            or isinstance(self.estimated_cost, bool)
            or not isinstance(self.estimated_cost, Real)
            or self.estimated_cost < 0
        ):
            raise ExecutionStorageCostProfileError(
                f"Cannot build an execution storage cost profile with a negative "
                f"estimated_cost: {self.estimated_cost!r}."
            )

        if self.calculated_at is None or not isinstance(self.calculated_at, datetime):
            raise ExecutionStorageCostProfileError(
                "Cannot build an execution storage cost profile with a non-datetime "
                "calculated_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionStorageCostProfileError(
                f"Cannot build an execution storage cost profile with an empty or blank "
                f"{field_name}."
            )
