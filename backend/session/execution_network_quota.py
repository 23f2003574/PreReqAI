from dataclasses import (
    dataclass,
)

from numbers import (
    Real,
)

from .execution_network_quota_error import (
    ExecutionNetworkQuotaError,
)


@dataclass(frozen=True)
class ExecutionNetworkQuota:
    """
    Immutable record of the bandwidth limits a runtime's network
    traffic is held to.

    The quota is a value object only. It performs no usage tracking
    or enforcement of its own; tracking consumption against these
    limits and resetting it is the responsibility of an execution
    network quota service, which produces a new record for every
    reconfiguration rather than mutating an existing one.

    Attributes:
        quota_id: The quota's unique identifier
        runtime_id: The identifier of the runtime this quota governs
        ingress_limit: The maximum amount of inbound traffic
            permitted per window
        egress_limit: The maximum amount of outbound traffic
            permitted per window
        window_seconds: The length, in seconds, of the rolling window
            usage is measured and reset against
        enabled: Whether this quota is currently enforced
    """

    quota_id: str

    runtime_id: str

    ingress_limit: float

    egress_limit: float

    window_seconds: float

    enabled: bool = True

    def __post_init__(self):
        self._require_text(self.quota_id, "quota ID")
        self._require_text(self.runtime_id, "runtime ID")

        self._require_positive(self.ingress_limit, "ingress_limit")
        self._require_positive(self.egress_limit, "egress_limit")
        self._require_positive(self.window_seconds, "window_seconds")

        if not isinstance(self.enabled, bool):
            raise ExecutionNetworkQuotaError(
                f"Cannot build an execution network quota with a non-boolean enabled: {self.enabled!r}."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionNetworkQuotaError(
                f"Cannot build an execution network quota with an empty or blank {field_name}."
            )

    @staticmethod
    def _require_positive(value, field_name: str) -> None:
        if value is None or isinstance(value, bool) or not isinstance(value, Real) or value <= 0:
            raise ExecutionNetworkQuotaError(
                f"Cannot build an execution network quota with a non-positive {field_name}: {value!r}."
            )
