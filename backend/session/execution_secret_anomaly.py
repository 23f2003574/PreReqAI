from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from typing import Any

from uuid import uuid4

from .execution_secret_anomaly_error import (
    ExecutionSecretAnomalyError,
)

from .execution_secret_anomaly_type import (
    ExecutionSecretAnomalyType,
)


@dataclass(frozen=True)
class ExecutionSecretAnomaly:
    """
    Immutable record of a single suspicious secret access pattern
    detected across execution sessions and principals.

    The anomaly is a value object only. It performs no detection of
    its own; detecting, listing, and resolving anomalies is the
    responsibility of an execution secret anomaly service.

    Attributes:
        anomaly_id: The anomaly's unique identifier
        secret_id: The identifier of the secret the anomaly concerns
        principal: Who or what the anomalous activity is attributed
            to
        anomaly_type: The kind of suspicious pattern detected, drawn
            from ExecutionSecretAnomalyType
        detected_at: When the anomaly was detected
        details: Supporting evidence for the anomaly, e.g. the
            audit event IDs it was detected from
    """

    secret_id: str

    principal: str

    anomaly_type: ExecutionSecretAnomalyType

    anomaly_id: str = field(
        default_factory=lambda: str(uuid4()),
    )

    detected_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    details: dict[str, Any] = field(
        default_factory=dict,
    )

    def __post_init__(self):
        self._require_text(self.anomaly_id, "anomaly ID")
        self._require_text(self.secret_id, "secret ID")
        self._require_text(self.principal, "principal")

        try:
            normalized_type = ExecutionSecretAnomalyType(self.anomaly_type)
        except ValueError as error:
            raise ExecutionSecretAnomalyError(
                f"Cannot build an execution secret anomaly with an invalid anomaly_type: {error}"
            ) from error

        object.__setattr__(self, "anomaly_type", normalized_type)

        if not isinstance(self.detected_at, datetime):
            raise ExecutionSecretAnomalyError(
                "Cannot build an execution secret anomaly with a non-datetime detected_at."
            )

        if not isinstance(self.details, dict):
            raise ExecutionSecretAnomalyError(
                "Cannot build an execution secret anomaly with a non-dict details."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionSecretAnomalyError(
                f"Cannot build an execution secret anomaly with an empty or blank {field_name}."
            )
