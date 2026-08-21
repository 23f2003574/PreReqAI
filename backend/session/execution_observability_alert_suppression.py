from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
)

from uuid import uuid4

from .execution_observability_alert_suppression_error import (
    ExecutionObservabilityAlertSuppressionError,
)


@dataclass(frozen=True)
class ExecutionObservabilityAlertSuppression:
    """
    Immutable record that alerts from a given rule and runtime are,
    for a bounded window, known and non-actionable.

    The suppression is a value object only. It performs no active
    tracking of its own; creating, checking, and revoking
    suppressions is the responsibility of an execution alert
    suppression service, which produces a new record for every
    transition (such as revocation) rather than mutating an existing
    one. A suppression is never deleted, so past suppressions remain
    auditable.

    Attributes:
        suppression_id: The suppression's unique identifier
        rule_id: The identifier of the alert rule this suppression
            applies to
        runtime_id: The identifier of the runtime this suppression
            applies to
        reason: A human-readable explanation of why the alert is
            being suppressed
        expires_at: When the suppression stops applying
        enabled: Whether the suppression is currently in force
            (False once explicitly revoked)
    """

    rule_id: str

    runtime_id: str

    reason: str

    expires_at: datetime

    suppression_id: str = field(default_factory=lambda: str(uuid4()))

    enabled: bool = True

    def __post_init__(self):
        self._require_text(self.suppression_id, "suppression ID")
        self._require_text(self.rule_id, "rule ID")
        self._require_text(self.runtime_id, "runtime ID")
        self._require_text(self.reason, "reason")

        if self.expires_at is None or not isinstance(self.expires_at, datetime):
            raise ExecutionObservabilityAlertSuppressionError(
                "Cannot build an execution observability alert suppression with a non-datetime expires_at."
            )

        if not isinstance(self.enabled, bool):
            raise ExecutionObservabilityAlertSuppressionError(
                "Cannot build an execution observability alert suppression with a non-boolean enabled."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionObservabilityAlertSuppressionError(
                f"Cannot build an execution observability alert suppression with an empty or blank {field_name}."
            )
