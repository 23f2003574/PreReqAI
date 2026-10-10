from dataclasses import (
    dataclass,
)

from numbers import (
    Real,
)

from .execution_storage_garbage_record import (
    RESOURCE_TYPES,
)

from .execution_storage_retention_policy_error import (
    ExecutionStorageRetentionPolicyError,
)


@dataclass(frozen=True)
class ExecutionStorageRetentionPolicy:
    """
    Immutable record of how long a scope's resources of a given type
    remain available before becoming eligible for garbage collection.

    The policy is a value object only. It performs no eligibility
    determination of its own; deciding whether a resource is
    currently eligible for collection is the responsibility of an
    execution storage retention service, which produces a new record
    for every reconfiguration or disablement rather than mutating an
    existing one.

    Attributes:
        policy_id: The policy's unique identifier
        scope_id: The identifier of the scope this policy governs
        resource_type: The kind of resource this policy governs, one
            of RESOURCE_TYPES (VOLUME, SNAPSHOT, REPLICA)
        retention_seconds: How long a resource of this type remains
            available before becoming eligible for collection; must
            be positive
        enabled: Whether this policy currently permits automatic
            collection
    """

    policy_id: str

    scope_id: str

    resource_type: str

    retention_seconds: float

    enabled: bool = True

    def __post_init__(self):
        self._require_text(self.policy_id, "policy ID")
        self._require_text(self.scope_id, "scope ID")

        if self.resource_type not in RESOURCE_TYPES:
            raise ExecutionStorageRetentionPolicyError(
                f"Cannot build an execution storage retention policy with an unknown "
                f"resource_type: {self.resource_type!r}."
            )

        if (
            self.retention_seconds is None
            or isinstance(self.retention_seconds, bool)
            or not isinstance(self.retention_seconds, Real)
            or self.retention_seconds <= 0
        ):
            raise ExecutionStorageRetentionPolicyError(
                f"Cannot build an execution storage retention policy with a non-positive "
                f"retention_seconds: {self.retention_seconds!r}."
            )

        if not isinstance(self.enabled, bool):
            raise ExecutionStorageRetentionPolicyError(
                f"Cannot build an execution storage retention policy with a non-boolean "
                f"enabled: {self.enabled!r}."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionStorageRetentionPolicyError(
                f"Cannot build an execution storage retention policy with an empty or blank "
                f"{field_name}."
            )
