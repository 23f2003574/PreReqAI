from dataclasses import (
    dataclass,
)

from numbers import (
    Real,
)

from .execution_storage_quota_error import (
    ExecutionStorageQuotaError,
)


@dataclass(frozen=True)
class ExecutionStorageQuota:
    """
    Immutable record of the persistent storage limit a scope's
    volumes are held to.

    The quota is a value object only. It performs no allocation
    tracking or enforcement of its own; tracking usage against this
    limit is the responsibility of an execution storage quota
    service, which produces a new record for every reconfiguration or
    usage change rather than mutating an existing one.

    Attributes:
        quota_id: The quota's unique identifier
        scope_id: The identifier of the scope this quota governs
        max_size: The maximum total storage size permitted
        used_size: The storage size currently allocated
        enabled: Whether this quota is currently enforced
    """

    quota_id: str

    scope_id: str

    max_size: float

    used_size: float = 0.0

    enabled: bool = True

    def __post_init__(self):
        self._require_text(self.quota_id, "quota ID")
        self._require_text(self.scope_id, "scope ID")

        if (
            self.max_size is None
            or isinstance(self.max_size, bool)
            or not isinstance(self.max_size, Real)
            or self.max_size <= 0
        ):
            raise ExecutionStorageQuotaError(
                f"Cannot build an execution storage quota with a non-positive max_size: {self.max_size!r}."
            )

        if (
            self.used_size is None
            or isinstance(self.used_size, bool)
            or not isinstance(self.used_size, Real)
            or self.used_size < 0
        ):
            raise ExecutionStorageQuotaError(
                f"Cannot build an execution storage quota with a negative used_size: {self.used_size!r}."
            )

        if self.used_size > self.max_size:
            raise ExecutionStorageQuotaError(
                f"Cannot build an execution storage quota with used_size ({self.used_size!r}) "
                f"exceeding max_size ({self.max_size!r})."
            )

        if not isinstance(self.enabled, bool):
            raise ExecutionStorageQuotaError(
                f"Cannot build an execution storage quota with a non-boolean enabled: {self.enabled!r}."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionStorageQuotaError(
                f"Cannot build an execution storage quota with an empty or blank {field_name}."
            )
