from dataclasses import (
    replace,
)

from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from .execution_observability_alert_suppression import (
    ExecutionObservabilityAlertSuppression,
)

from .execution_observability_alert_suppression_error import (
    ExecutionObservabilityAlertSuppressionError,
)


class ExecutionAlertSuppressionService:
    """
    Temporarily suppresses known, non-actionable alerts for a given
    alert rule and runtime, without deleting suppression history or
    touching any previously triggered alert.

    Composes with nothing: suppression is tracked entirely as its own
    registry, keyed by rule_id and runtime_id. It never reads from or
    mutates an alert or alert rule service, so suppressing a rule can
    never affect alerts already recorded against it.

    Behavior:
    - suppress() creates a new, enabled suppression; reason and
      expires_at are both required
    - is_suppressed() reports whether rule_id/runtime_id currently
      has an in-force suppression (enabled and not yet expired)
    - active() reports a runtime's currently in-force suppressions
    - revoke() is idempotent: revoking an already-revoked suppression
      simply returns it unchanged; revocation never deletes the
      record, so it remains auditable
    - expired() reports every still-enabled suppression whose
      expires_at has passed, across every runtime

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self):
        self._suppressions_by_id = {}
        self._lock = RLock()

    def suppress(
        self, rule_id: str, runtime_id: str, reason: str, expires_at: datetime
    ) -> ExecutionObservabilityAlertSuppression:
        """
        Create a new, enabled suppression for rule_id and runtime_id.

        Raises:
            ExecutionObservabilityAlertSuppressionError: If rule_id,
                runtime_id, or reason is None or blank, or expires_at
                is not a datetime
        """

        self._validate_text(rule_id, "rule ID")
        self._validate_text(runtime_id, "runtime ID")
        self._validate_text(reason, "reason")

        suppression = ExecutionObservabilityAlertSuppression(
            rule_id=rule_id,
            runtime_id=runtime_id,
            reason=reason,
            expires_at=expires_at,
        )

        with self._lock:
            self._suppressions_by_id[suppression.suppression_id] = suppression

            return suppression

    def is_suppressed(self, rule_id: str, runtime_id: str) -> bool:
        """
        Whether rule_id/runtime_id currently has an in-force
        suppression.

        Raises:
            ExecutionObservabilityAlertSuppressionError: If rule_id
                or runtime_id is None or blank
        """

        self._validate_text(rule_id, "rule ID")
        self._validate_text(runtime_id, "runtime ID")

        now = datetime.now(timezone.utc)

        with self._lock:
            candidates = list(self._suppressions_by_id.values())

        return any(
            suppression.rule_id == rule_id
            and suppression.runtime_id == runtime_id
            and self._is_active(suppression, now)
            for suppression in candidates
        )

    def active(self, runtime_id: str) -> tuple:
        """
        runtime_id's currently in-force suppressions, soonest to
        expire first.

        Raises:
            ExecutionObservabilityAlertSuppressionError: If
                runtime_id is None or blank
        """

        self._validate_text(runtime_id, "runtime ID")

        now = datetime.now(timezone.utc)

        with self._lock:
            candidates = list(self._suppressions_by_id.values())

        matching = [
            suppression
            for suppression in candidates
            if suppression.runtime_id == runtime_id and self._is_active(suppression, now)
        ]

        return tuple(sorted(matching, key=lambda suppression: suppression.expires_at))

    def revoke(self, suppression_id: str) -> ExecutionObservabilityAlertSuppression:
        """
        Revoke a suppression. Idempotent: revoking an
        already-revoked suppression simply returns it unchanged. The
        record itself is never removed, so it remains auditable.

        Raises:
            ExecutionObservabilityAlertSuppressionError: If
                suppression_id is None or blank, or no suppression is
                registered under it
        """

        self._validate_text(suppression_id, "suppression ID")

        with self._lock:
            suppression = self._resolve(suppression_id)

            if not suppression.enabled:
                return suppression

            revoked = replace(suppression, enabled=False)
            self._suppressions_by_id[suppression_id] = revoked

            return revoked

    def expired(self) -> tuple:
        """
        Every still-enabled suppression whose expires_at has passed,
        soonest-expired first.
        """

        now = datetime.now(timezone.utc)

        with self._lock:
            candidates = list(self._suppressions_by_id.values())

        matching = [
            suppression
            for suppression in candidates
            if suppression.enabled and suppression.expires_at <= now
        ]

        return tuple(sorted(matching, key=lambda suppression: suppression.expires_at))

    @staticmethod
    def _is_active(suppression: ExecutionObservabilityAlertSuppression, now: datetime) -> bool:
        return suppression.enabled and suppression.expires_at > now

    def _resolve(self, suppression_id: str) -> ExecutionObservabilityAlertSuppression:
        suppression = self._suppressions_by_id.get(suppression_id)

        if suppression is None:
            raise ExecutionObservabilityAlertSuppressionError(
                f"No suppression is recorded under suppression ID {suppression_id!r}."
            )

        return suppression

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionObservabilityAlertSuppressionError(
                f"Cannot use an empty or blank {field_name}."
            )
