from dataclasses import (
    dataclass,
)

from datetime import (
    datetime,
)

from .execution_observability_alert_fingerprint_error import (
    ExecutionObservabilityAlertFingerprintError,
)


@dataclass(frozen=True)
class ExecutionObservabilityAlertFingerprint:
    """
    Immutable record tracking how many times a given runtime and rule
    combination has triggered, collapsed under a single fingerprint
    so repeats do not flood the observability pipeline.

    The fingerprint record is a value object only. It performs no
    deduplication of its own; computing fingerprints and recording
    occurrences is the responsibility of an execution alert
    deduplication service, which produces a new record for every
    occurrence rather than mutating an existing one.

    Attributes:
        fingerprint: The deterministic identifier for this runtime
            and rule combination
        runtime_id: The identifier of the runtime the alert was
            triggered for
        rule_id: The identifier of the rule the alert was triggered
            from
        first_seen: When this fingerprint was first recorded
        last_seen: When this fingerprint was most recently recorded
        occurrence_count: How many times this fingerprint has been
            recorded
    """

    fingerprint: str

    runtime_id: str

    rule_id: str

    first_seen: datetime

    last_seen: datetime

    occurrence_count: int = 1

    def __post_init__(self):
        self._require_text(self.fingerprint, "fingerprint")
        self._require_text(self.runtime_id, "runtime ID")
        self._require_text(self.rule_id, "rule ID")

        if self.first_seen is None or not isinstance(self.first_seen, datetime):
            raise ExecutionObservabilityAlertFingerprintError(
                "Cannot build an execution observability alert fingerprint with a non-datetime first_seen."
            )

        if self.last_seen is None or not isinstance(self.last_seen, datetime):
            raise ExecutionObservabilityAlertFingerprintError(
                "Cannot build an execution observability alert fingerprint with a non-datetime last_seen."
            )

        if self.last_seen < self.first_seen:
            raise ExecutionObservabilityAlertFingerprintError(
                "Cannot build an execution observability alert fingerprint with last_seen before first_seen."
            )

        if (
            isinstance(self.occurrence_count, bool)
            or not isinstance(self.occurrence_count, int)
            or self.occurrence_count < 1
        ):
            raise ExecutionObservabilityAlertFingerprintError(
                f"Cannot build an execution observability alert fingerprint with a non-positive "
                f"occurrence_count: {self.occurrence_count!r}."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionObservabilityAlertFingerprintError(
                f"Cannot build an execution observability alert fingerprint with an empty or blank {field_name}."
            )
