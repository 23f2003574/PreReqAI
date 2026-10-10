from dataclasses import (
    replace,
)

from threading import (
    RLock,
)

from .execution_secret_security_policy import (
    ExecutionSecretSecurityPolicy,
)

from .execution_secret_security_policy_error import (
    ExecutionSecretSecurityPolicyError,
)

from .execution_secret_trust_level import (
    ExecutionSecretTrustLevel,
)


class ExecutionSecretSecurityPolicyService:
    """
    Defines and enforces which security controls are mandatory for a
    secret, using an existing execution secret rotation service,
    lease service, trust service, access policy service, and audit
    service as the sources of truth for whether each control is
    currently in place.

    The service's responsibility is policy bookkeeping and
    enforcement checks only. It never mutates any of the services it
    reads from, and it never grants or denies secret access itself; a
    caller is expected to call validate() before secret access and
    honor the result.

    A secret may have any number of registered policies; an enabled
    policy's requirements are additive, so a requirement is enforced
    if any enabled policy for the secret turns it on. A secret with
    no enabled policy at all has nothing to satisfy.

    Checks, always run in this fixed order, so results are
    deterministic for the same underlying state:
    - missing_rotation: require_rotation is on, but the secret has no
      recorded rotation history
    - missing_lease: require_lease is on, but the secret has no
      currently active lease
    - missing_trust: require_trust is on, but the secret has no
      enabled access grant, or a principal it grants access to is
      only trusted at LOW
    - missing_audit: require_audit is on, but the secret has no
      recorded audit history

    Behavior:
    - violations() always returns every unmet, enabled requirement,
      never just the first
    - disable() takes effect immediately: a disabled policy is
      ignored entirely by validate() and violations()

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(
        self,
        execution_secret_rotation_service,
        execution_secret_lease_service,
        execution_secret_trust_service,
        execution_secret_access_service,
        execution_secret_audit_service,
    ):
        """
        Args:
            execution_secret_rotation_service: Read via
                `history(secret_id)` to check require_rotation
            execution_secret_lease_service: Read via
                `active(secret_id)` to check require_lease
            execution_secret_trust_service: Read via `trust(principal)`
                to check require_trust
            execution_secret_access_service: Read via
                `policies(secret_id)` for the principals require_trust
                checks
            execution_secret_audit_service: Read via
                `history(secret_id)` to check require_audit
        """

        self._execution_secret_rotation_service = execution_secret_rotation_service
        self._execution_secret_lease_service = execution_secret_lease_service
        self._execution_secret_trust_service = execution_secret_trust_service
        self._execution_secret_access_service = execution_secret_access_service
        self._execution_secret_audit_service = execution_secret_audit_service
        self._policies_by_id = {}
        self._policy_ids_by_secret = {}
        self._lock = RLock()

    def register(self, policy: ExecutionSecretSecurityPolicy) -> ExecutionSecretSecurityPolicy:
        """
        Register a security policy.

        Raises:
            ExecutionSecretSecurityPolicyError: If policy is not an
                ExecutionSecretSecurityPolicy, or its policy ID is
                already registered
        """

        if not isinstance(policy, ExecutionSecretSecurityPolicy):
            raise ExecutionSecretSecurityPolicyError(
                "Cannot register an invalid policy: policy must be an ExecutionSecretSecurityPolicy."
            )

        with self._lock:
            if policy.policy_id in self._policies_by_id:
                raise ExecutionSecretSecurityPolicyError(f"Policy ID {policy.policy_id!r} is already registered.")

            self._policies_by_id[policy.policy_id] = policy
            self._policy_ids_by_secret.setdefault(policy.secret_id, []).append(policy.policy_id)

            return policy

    def validate(self, secret_id: str) -> bool:
        """
        Check whether a secret currently satisfies every requirement
        enabled across its registered policies.

        Raises:
            ExecutionSecretSecurityPolicyError: If secret_id is None
                or blank
        """

        self._validate_id(secret_id, "secret ID")

        with self._lock:
            return not self._violations(secret_id)

    def violations(self, secret_id: str) -> list:
        """
        List every unmet, enabled requirement for a secret, in the
        fixed order they are checked.

        Raises:
            ExecutionSecretSecurityPolicyError: If secret_id is None
                or blank
        """

        self._validate_id(secret_id, "secret ID")

        with self._lock:
            return self._violations(secret_id)

    def disable(self, policy_id: str) -> ExecutionSecretSecurityPolicy:
        """
        Disable a registered policy, so it is ignored entirely by
        validate() and violations().

        Raises:
            ExecutionSecretSecurityPolicyError: If policy_id is None
                or blank, or no policy is registered under it
        """

        self._validate_id(policy_id, "policy ID")

        with self._lock:
            policy = self._resolve(policy_id)

            updated = replace(policy, enabled=False)
            self._policies_by_id[policy_id] = updated

            return updated

    def _violations(self, secret_id: str) -> list:
        enabled_policies = [
            self._policies_by_id[policy_id]
            for policy_id in self._policy_ids_by_secret.get(secret_id, [])
            if self._policies_by_id[policy_id].enabled
        ]

        require_rotation = any(policy.require_rotation for policy in enabled_policies)
        require_lease = any(policy.require_lease for policy in enabled_policies)
        require_trust = any(policy.require_trust for policy in enabled_policies)
        require_audit = any(policy.require_audit for policy in enabled_policies)

        violations = []

        if require_rotation and not self._execution_secret_rotation_service.history(secret_id):
            violations.append("missing_rotation")

        if require_lease and not self._execution_secret_lease_service.active(secret_id):
            violations.append("missing_lease")

        if require_trust and not self._has_adequate_trust(secret_id):
            violations.append("missing_trust")

        if require_audit and not self._execution_secret_audit_service.history(secret_id):
            violations.append("missing_audit")

        return violations

    def _has_adequate_trust(self, secret_id: str) -> bool:
        granted_principals = sorted(
            {
                policy.principal
                for policy in self._execution_secret_access_service.policies(secret_id)
                if policy.enabled
            }
        )

        if not granted_principals:
            return False

        return all(
            self._execution_secret_trust_service.trust(principal) != ExecutionSecretTrustLevel.LOW
            for principal in granted_principals
        )

    def _resolve(self, policy_id: str) -> ExecutionSecretSecurityPolicy:
        policy = self._policies_by_id.get(policy_id)

        if policy is None:
            raise ExecutionSecretSecurityPolicyError(f"No policy is registered under policy ID {policy_id!r}.")

        return policy

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionSecretSecurityPolicyError(f"Cannot use an empty or blank {field_name}.")
