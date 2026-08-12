from threading import (
    RLock,
)

from .execution_secret_posture_error import (
    ExecutionSecretPostureError,
)

from .execution_secret_posture_level import (
    ExecutionSecretPostureLevel,
)

from .execution_secret_security_posture import (
    ExecutionSecretSecurityPosture,
)

from .execution_secret_trust_level import (
    ExecutionSecretTrustLevel,
)


class ExecutionSecretSecurityPostureService:
    """
    Computes a security posture for a secret from its access, trust,
    lease, rotation, and revocation state, using an existing
    execution secret access policy service, trust service, lease
    service, (value) rotation service, revocation service, and audit
    service as the sources of truth for each.

    The service's responsibility is evaluation only. It never
    mutates any of the services it reads from; evaluate() is a pure
    computation over whatever state already exists at the moment it
    is called.

    Checks, always run in this fixed order, so results are
    deterministic for the same underlying state:
    - no_access_policy: the secret has no enabled access policy
      granting anyone access
    - low_trust_principal:<principal>: a principal with an enabled
      access policy on the secret is only trusted at LOW, for each
      such principal in sorted order
    - uncleaned_expired_lease: the secret has a lease that is past
      expiry but not yet cleaned up
    - never_rotated: the secret has no recorded rotation history
    - secret_revoked: the secret is currently revoked

    Behavior:
    - A currently revoked secret is always COMPROMISED, regardless of
      any other check
    - A secret with no violations is SECURE; one with violations but
      not revoked is DEGRADED

    The service is:
    - Thread-safe: All reads are guarded by an internal lock
    """

    def __init__(
        self,
        execution_secret_access_service,
        execution_secret_trust_service,
        execution_secret_lease_service,
        execution_secret_rotation_service,
        execution_secret_revocation_service,
        execution_secret_audit_service,
    ):
        """
        Args:
            execution_secret_access_service: Read via
                `policies(secret_id)` for the secret's access grants
            execution_secret_trust_service: Read via `trust(principal)`
                for each principal with an enabled access grant
            execution_secret_lease_service: Read via `expired()` for
                the secret's uncleaned expired leases
            execution_secret_rotation_service: Read via
                `history(secret_id)` for the secret's rotation history
            execution_secret_revocation_service: Read via
                `is_revoked(secret_id)` for the secret's revocation
                status
            execution_secret_audit_service: Read via
                `session_history(session_id)` to discover which
                secrets a session has touched, for evaluate_session()
        """

        self._execution_secret_access_service = execution_secret_access_service
        self._execution_secret_trust_service = execution_secret_trust_service
        self._execution_secret_lease_service = execution_secret_lease_service
        self._execution_secret_rotation_service = execution_secret_rotation_service
        self._execution_secret_revocation_service = execution_secret_revocation_service
        self._execution_secret_audit_service = execution_secret_audit_service
        self._lock = RLock()

    def evaluate(self, secret_id: str) -> ExecutionSecretSecurityPosture:
        """
        Compute a secret's current security posture.

        Raises:
            ExecutionSecretPostureError: If secret_id is None or
                blank
        """

        self._validate_id(secret_id, "secret ID")

        with self._lock:
            return self._evaluate(secret_id)

    def evaluate_session(self, session_id: str) -> list:
        """
        Compute a security posture for every secret a session's
        recorded audit history has touched, in the order each secret
        was first referenced.

        Raises:
            ExecutionSecretPostureError: If session_id is None or
                blank
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            secret_ids = []

            for event in self._execution_secret_audit_service.session_history(session_id):
                if event.secret_id not in secret_ids:
                    secret_ids.append(event.secret_id)

            return [self._evaluate(secret_id) for secret_id in secret_ids]

    def violations(self, secret_id: str) -> list:
        """
        List a secret's current violations, in the fixed order they
        are checked.

        Raises:
            ExecutionSecretPostureError: If secret_id is None or
                blank
        """

        self._validate_id(secret_id, "secret ID")

        with self._lock:
            return list(self._evaluate(secret_id).violations)

    def _evaluate(self, secret_id: str) -> ExecutionSecretSecurityPosture:
        violations = []

        enabled_principals = sorted(
            {
                policy.principal
                for policy in self._execution_secret_access_service.policies(secret_id)
                if policy.enabled
            }
        )

        if not enabled_principals:
            violations.append("no_access_policy")

        for principal in enabled_principals:
            if self._execution_secret_trust_service.trust(principal) == ExecutionSecretTrustLevel.LOW:
                violations.append(f"low_trust_principal:{principal}")

        if any(lease.secret_id == secret_id for lease in self._execution_secret_lease_service.expired()):
            violations.append("uncleaned_expired_lease")

        if not self._execution_secret_rotation_service.history(secret_id):
            violations.append("never_rotated")

        revoked = self._execution_secret_revocation_service.is_revoked(secret_id)

        if revoked:
            violations.append("secret_revoked")
            level = ExecutionSecretPostureLevel.COMPROMISED
        elif violations:
            level = ExecutionSecretPostureLevel.DEGRADED
        else:
            level = ExecutionSecretPostureLevel.SECURE

        return ExecutionSecretSecurityPosture(
            secret_id=secret_id,
            level=level,
            violations=tuple(violations),
        )

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionSecretPostureError(f"Cannot use an empty or blank {field_name}.")
