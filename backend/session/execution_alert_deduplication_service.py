from dataclasses import (
    replace,
)

from datetime import (
    datetime,
)

from hashlib import (
    sha256,
)

from threading import (
    RLock,
)

from .execution_observability_alert_fingerprint import (
    ExecutionObservabilityAlertFingerprint,
)

from .execution_observability_alert_fingerprint_error import (
    ExecutionObservabilityAlertFingerprintError,
)


class ExecutionAlertDeduplicationService:
    """
    Prevents identical runtime alerts from flooding the observability
    pipeline by collapsing repeated triggers of the same rule against
    the same runtime into a single fingerprinted occurrence count.

    Fingerprinting is a pure function of an alert's runtime_id and
    rule_id (duck-typed: anything exposing `.runtime_id`, `.rule_id`,
    and `.triggered_at`, matching ExecutionObservabilityAlert) — a
    rule_id always refers to the same triggering condition once
    triggered, so runtime_id plus rule_id together fully identify it.
    The alert's observed value is deliberately excluded: repeated
    triggers of the same rule with a different value are still the
    same recurring alert, not a distinct one.

    Behavior:
    - fingerprint() is a pure, deterministic function: the same
      runtime_id/rule_id pair always produces the same fingerprint,
      and a different runtime_id or rule_id always produces a
      different one
    - record() creates a new fingerprint entry on first occurrence
      (occurrence_count 1, first_seen == last_seen == the alert's
      triggered_at), or increments occurrence_count and advances
      last_seen on every later occurrence, leaving first_seen
      untouched
    - duplicate() reports whether an alert's fingerprint has already
      been recorded, without recording it itself
    - occurrences() reports a fingerprint's current occurrence_count,
      or 0 if it has never been recorded
    - reset() clears a fingerprint's tracked occurrences entirely, so
      its next record() starts a fresh count; idempotent when the
      fingerprint is not currently tracked

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self):
        self._fingerprints_by_key = {}
        self._lock = RLock()

    def fingerprint(self, alert) -> str:
        """
        The deterministic fingerprint for alert's runtime_id and
        rule_id.

        Raises:
            ExecutionObservabilityAlertFingerprintError: If alert has
                no non-blank runtime_id or rule_id, or no datetime
                triggered_at
        """

        self._validate_alert(alert)

        return self._compute_fingerprint(alert.runtime_id, alert.rule_id)

    def record(self, alert) -> ExecutionObservabilityAlertFingerprint:
        """
        Record an occurrence of alert. Creates a new fingerprint
        entry on first occurrence, or increments the existing one's
        occurrence_count and advances last_seen.

        Raises:
            ExecutionObservabilityAlertFingerprintError: If alert has
                no non-blank runtime_id or rule_id, or no datetime
                triggered_at
        """

        self._validate_alert(alert)

        key = self._compute_fingerprint(alert.runtime_id, alert.rule_id)

        with self._lock:
            existing = self._fingerprints_by_key.get(key)

            if existing is None:
                record = ExecutionObservabilityAlertFingerprint(
                    fingerprint=key,
                    runtime_id=alert.runtime_id,
                    rule_id=alert.rule_id,
                    first_seen=alert.triggered_at,
                    last_seen=alert.triggered_at,
                    occurrence_count=1,
                )
            else:
                record = replace(
                    existing,
                    last_seen=alert.triggered_at,
                    occurrence_count=existing.occurrence_count + 1,
                )

            self._fingerprints_by_key[key] = record

            return record

    def duplicate(self, alert) -> bool:
        """
        Whether alert's fingerprint has already been recorded.
        Does not record it itself.

        Raises:
            ExecutionObservabilityAlertFingerprintError: If alert has
                no non-blank runtime_id or rule_id, or no datetime
                triggered_at
        """

        self._validate_alert(alert)

        key = self._compute_fingerprint(alert.runtime_id, alert.rule_id)

        with self._lock:
            return key in self._fingerprints_by_key

    def occurrences(self, fingerprint: str) -> int:
        """
        fingerprint's current occurrence_count, or 0 if it has never
        been recorded.

        Raises:
            ExecutionObservabilityAlertFingerprintError: If
                fingerprint is None or blank
        """

        self._validate_text(fingerprint, "fingerprint")

        with self._lock:
            record = self._fingerprints_by_key.get(fingerprint)

            return record.occurrence_count if record is not None else 0

    def reset(self, fingerprint: str):
        """
        Clear fingerprint's tracked occurrences entirely, so its next
        record() starts a fresh count. Idempotent: resetting a
        fingerprint that is not currently tracked simply returns
        None.

        Raises:
            ExecutionObservabilityAlertFingerprintError: If
                fingerprint is None or blank
        """

        self._validate_text(fingerprint, "fingerprint")

        with self._lock:
            return self._fingerprints_by_key.pop(fingerprint, None)

    @staticmethod
    def _compute_fingerprint(runtime_id: str, rule_id: str) -> str:
        digest_input = f"{runtime_id}:{rule_id}".encode("utf-8")

        return sha256(digest_input).hexdigest()

    @classmethod
    def _validate_alert(cls, alert) -> None:
        cls._validate_text(getattr(alert, "runtime_id", None), "runtime ID")
        cls._validate_text(getattr(alert, "rule_id", None), "rule ID")

        triggered_at = getattr(alert, "triggered_at", None)

        if triggered_at is None or not isinstance(triggered_at, datetime):
            raise ExecutionObservabilityAlertFingerprintError(
                "Cannot fingerprint an alert with a non-datetime triggered_at."
            )

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionObservabilityAlertFingerprintError(
                f"Cannot use an empty or blank {field_name}."
            )
