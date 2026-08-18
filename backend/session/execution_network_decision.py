from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from .execution_network_decision_error import (
    ExecutionNetworkDecisionError,
)


@dataclass(frozen=True)
class ExecutionNetworkDecision:
    """
    Immutable record of the outcome of running a runtime's traffic
    through the full network decision pipeline once.

    The decision is a value object only. It performs no evaluation of
    its own; running the pipeline (traffic policy, endpoint health and
    circuit state, connection limits, quota and shaping, and failover)
    and producing this record is the responsibility of an execution
    network orchestration service, which produces a new record for
    every connect, evaluate, reroute, or disconnect rather than
    mutating an existing one.

    Attributes:
        decision_id: The decision's unique identifier
        runtime_id: The identifier of the runtime this decision was
            made for
        endpoint_id: The endpoint the decision concerns, or None when
            no endpoint was available or applicable
        allowed: Whether the runtime's traffic was permitted
        reason: A short, human-readable explanation for the outcome
        created_at: When this decision was made
    """

    decision_id: str

    runtime_id: str

    endpoint_id: str

    allowed: bool

    reason: str

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        self._require_text(self.decision_id, "decision ID")
        self._require_text(self.runtime_id, "runtime ID")
        self._require_text(self.reason, "reason")

        if self.endpoint_id is not None:
            self._require_text(self.endpoint_id, "endpoint ID")

        if not isinstance(self.allowed, bool):
            raise ExecutionNetworkDecisionError(
                f"Cannot build an execution network decision with a non-boolean allowed: "
                f"{self.allowed!r}."
            )

        if self.created_at is None or not isinstance(self.created_at, datetime):
            raise ExecutionNetworkDecisionError(
                "Cannot build an execution network decision with a non-datetime created_at."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionNetworkDecisionError(
                f"Cannot build an execution network decision with an empty or blank {field_name}."
            )
