from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from .execution_storage_tier_error import (
    ExecutionStorageTierError,
)

TIER_HOT = "HOT"

TIER_WARM = "WARM"

TIER_COLD = "COLD"

TIERS = (
    TIER_HOT,
    TIER_WARM,
    TIER_COLD,
)


@dataclass(frozen=True)
class ExecutionStorageTier:
    """
    Immutable record of a resource's storage tier as of a single,
    explicit transition.

    The record is a value object only. It performs no evaluation or
    transition of its own; classifying resources and moving them
    between tiers is the responsibility of an execution storage
    tiering service, which produces a new record for every transition
    rather than mutating an existing one.

    Attributes:
        tier_id: The record's unique identifier
        resource_id: The identifier of the resource this record
            describes
        tier: The resource's tier as of this record, one of TIERS
        last_accessed: When the resource was last accessed, as of
            this record
        transitioned_at: When this transition was made
    """

    tier_id: str

    resource_id: str

    tier: str

    last_accessed: datetime

    transitioned_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        self._require_text(self.tier_id, "tier ID")
        self._require_text(self.resource_id, "resource ID")

        if self.tier not in TIERS:
            raise ExecutionStorageTierError(
                f"Cannot build an execution storage tier with an unknown tier: {self.tier!r}."
            )

        if self.last_accessed is None or not isinstance(self.last_accessed, datetime):
            raise ExecutionStorageTierError(
                "Cannot build an execution storage tier with a non-datetime last_accessed."
            )

        if self.transitioned_at is None or not isinstance(self.transitioned_at, datetime):
            raise ExecutionStorageTierError(
                "Cannot build an execution storage tier with a non-datetime transitioned_at."
            )

        if self.transitioned_at < self.last_accessed:
            raise ExecutionStorageTierError(
                "Cannot build an execution storage tier transitioned before its last_accessed."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionStorageTierError(
                f"Cannot build an execution storage tier with an empty or blank {field_name}."
            )
