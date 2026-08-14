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

from uuid import uuid4

from .execution_policy_risk_override import (
    ExecutionPolicyRiskOverride,
)

from .execution_policy_risk_override_error import (
    ExecutionPolicyRiskOverrideError,
)


class ExecutionPolicyRiskOverrideService:
    """
    Grants explicitly approved, time-bound tolerance for a session's
    risk level, without modifying the risk score or thresholds an
    existing execution policy risk service and risk threshold
    service produce.

    An override never raises what a session is permitted: it can
    never tolerate more than MAXIMUM_OVERRIDABLE_LEVEL, so the most
    severe risk level can never be overridden away.

    Behavior:
    - create() requires a non-blank reason and a non-None
      expires_at; an override can never be created without either
    - An override is active only while it is enabled and not past
      its expires_at; revoking or letting it expire never deletes
      its record or its reason
    - active() lists only the overrides currently active for a
      session
    - expired() lists every recorded override whose expires_at has
      passed, regardless of session or revocation

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self):
        self._overrides_by_id = {}
        self._override_ids_by_session = {}
        self._lock = RLock()

    def create(
        self,
        session_id: str,
        maximum_level: str,
        reason: str,
        expires_at: datetime,
    ) -> ExecutionPolicyRiskOverride:
        """
        Create a new override.

        Raises:
            ExecutionPolicyRiskOverrideError: If reason is blank,
                expires_at is None, maximum_level exceeds
                MAXIMUM_OVERRIDABLE_LEVEL, or any other field is
                invalid
        """

        with self._lock:
            override = ExecutionPolicyRiskOverride(
                override_id=str(uuid4()),
                session_id=session_id,
                maximum_level=maximum_level,
                reason=reason,
                expires_at=expires_at,
            )

            self._overrides_by_id[override.override_id] = override
            self._override_ids_by_session.setdefault(session_id, []).append(override.override_id)

            return override

    def validate(self, override_id: str) -> bool:
        """
        Check whether an override is currently active.

        Raises:
            ExecutionPolicyRiskOverrideError: If override_id is None
                or blank, or no override is recorded under it
        """

        self._validate_text(override_id, "override ID")

        with self._lock:
            return self._is_active(self._resolve(override_id))

    def active(self, session_id: str) -> list:
        """
        List the currently active overrides for a session.

        Raises:
            ExecutionPolicyRiskOverrideError: If session_id is None
                or blank
        """

        self._validate_text(session_id, "session ID")

        with self._lock:
            return [
                self._overrides_by_id[override_id]
                for override_id in self._override_ids_by_session.get(session_id, [])
                if self._is_active(self._overrides_by_id[override_id])
            ]

    def revoke(self, override_id: str) -> ExecutionPolicyRiskOverride:
        """
        Revoke an override, so it is inactive immediately, even if
        it has not yet expired.

        Raises:
            ExecutionPolicyRiskOverrideError: If override_id is None
                or blank, or no override is recorded under it
        """

        self._validate_text(override_id, "override ID")

        with self._lock:
            override = self._resolve(override_id)

            updated = replace(override, enabled=False)
            self._overrides_by_id[override_id] = updated

            return updated

    def expired(self) -> list:
        """
        List every recorded override whose expires_at has passed,
        regardless of session or revocation.
        """

        with self._lock:
            now = datetime.now(timezone.utc)

            return [override for override in self._overrides_by_id.values() if override.expires_at <= now]

    def _is_active(self, override: ExecutionPolicyRiskOverride) -> bool:
        if not override.enabled:
            return False

        return override.expires_at > datetime.now(timezone.utc)

    def _resolve(self, override_id: str) -> ExecutionPolicyRiskOverride:
        override = self._overrides_by_id.get(override_id)

        if override is None:
            raise ExecutionPolicyRiskOverrideError(f"No override is recorded under override ID {override_id!r}.")

        return override

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionPolicyRiskOverrideError(f"Cannot use an empty or blank {field_name}.")
