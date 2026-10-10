from dataclasses import (
    replace,
)

from threading import (
    RLock,
)

from .execution_secret_operation import (
    ExecutionSecretOperation,
)

from .execution_secret_trust_error import (
    ExecutionSecretTrustError,
)

from .execution_secret_trust_level import (
    ExecutionSecretTrustLevel,
)

from .execution_secret_trust_policy import (
    ExecutionSecretTrustPolicy,
)

_TRUST_RANK = {
    ExecutionSecretTrustLevel.LOW: 1,
    ExecutionSecretTrustLevel.STANDARD: 2,
    ExecutionSecretTrustLevel.HIGH: 3,
}

_OPERATION_RISK = {
    ExecutionSecretOperation.READ: 1,
    ExecutionSecretOperation.ROTATE: 2,
    ExecutionSecretOperation.DELETE: 3,
}


class ExecutionSecretTrustService:
    """
    Defines trust levels for principals accessing execution secrets,
    independent of any specific secret: a principal's trust reflects
    who they are, not which secret they are touching.

    The service's responsibility is trust policy bookkeeping and
    authorization checks only. It does not resolve or store raw
    secret values, and it does not itself grant access to any
    specific secret; a caller is expected to combine authorize() with
    whatever per-secret access policy already governs a secret.

    Behavior:
    - A principal may have any number of registered policies; trust()
      reflects the highest trust_level among their enabled policies,
      or LOW if none are registered or enabled
    - A trust level inherits every lower-risk operation on its own:
      STANDARD inherits READ, HIGH inherits READ and ROTATE. The
      riskiest operation available at each level, DELETE, is never
      inherited; it is only ever granted by an explicit
      allowed_operations entry
    - authorize() also honors whatever allowed_operations any enabled
      policy explicitly grants the principal, on top of inheritance
    - disable() takes effect immediately: a disabled policy
      contributes nothing to trust() or authorize()

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self):
        self._policies_by_id = {}
        self._policy_ids_by_principal = {}
        self._lock = RLock()

    def register(self, policy: ExecutionSecretTrustPolicy) -> ExecutionSecretTrustPolicy:
        """
        Register a trust policy.

        Raises:
            ExecutionSecretTrustError: If policy is not an
                ExecutionSecretTrustPolicy, or its policy ID is
                already registered
        """

        if not isinstance(policy, ExecutionSecretTrustPolicy):
            raise ExecutionSecretTrustError(
                "Cannot register an invalid policy: policy must be an ExecutionSecretTrustPolicy."
            )

        with self._lock:
            if policy.policy_id in self._policies_by_id:
                raise ExecutionSecretTrustError(f"Policy ID {policy.policy_id!r} is already registered.")

            self._policies_by_id[policy.policy_id] = policy
            self._policy_ids_by_principal.setdefault(policy.principal, []).append(policy.policy_id)

            return policy

    def trust(self, principal: str) -> ExecutionSecretTrustLevel:
        """
        Look up a principal's current trust level: the highest
        trust_level among their enabled policies, or LOW if they have
        none.

        Raises:
            ExecutionSecretTrustError: If principal is None or blank
        """

        self._validate_id(principal, "principal")

        with self._lock:
            return self._trust(principal)

    def authorize(self, principal: str, operation) -> bool:
        """
        Check whether a principal is currently authorized to perform
        an operation, either because an enabled policy explicitly
        grants it or because it is inherited from their trust level.

        Raises:
            ExecutionSecretTrustError: If principal is None or blank,
                or operation is not a valid ExecutionSecretOperation
        """

        self._validate_id(principal, "principal")

        try:
            normalized_operation = ExecutionSecretOperation(operation)
        except ValueError as error:
            raise ExecutionSecretTrustError(f"Invalid operation {operation!r}.") from error

        with self._lock:
            for policy in self._enabled_policies(principal):
                if normalized_operation in policy.allowed_operations:
                    return True

            trust_level = self._trust(principal)

            return _OPERATION_RISK[normalized_operation] < _TRUST_RANK[trust_level]

    def disable(self, policy_id: str) -> ExecutionSecretTrustPolicy:
        """
        Disable a registered policy, so it no longer contributes to
        trust() or authorize().

        Raises:
            ExecutionSecretTrustError: If policy_id is None or blank,
                or no policy is registered under it
        """

        self._validate_id(policy_id, "policy ID")

        with self._lock:
            policy = self._resolve(policy_id)

            updated = replace(policy, enabled=False)
            self._policies_by_id[policy_id] = updated

            return updated

    def policies(self, principal: str) -> list:
        """
        List every policy ever registered for a principal, in the
        order they were registered.

        Raises:
            ExecutionSecretTrustError: If principal is None or blank
        """

        self._validate_id(principal, "principal")

        with self._lock:
            return [
                self._policies_by_id[policy_id]
                for policy_id in self._policy_ids_by_principal.get(principal, [])
            ]

    def _trust(self, principal: str) -> ExecutionSecretTrustLevel:
        enabled_policies = self._enabled_policies(principal)

        if not enabled_policies:
            return ExecutionSecretTrustLevel.LOW

        return max(
            (policy.trust_level for policy in enabled_policies),
            key=lambda trust_level: _TRUST_RANK[trust_level],
        )

    def _enabled_policies(self, principal: str) -> list:
        return [
            self._policies_by_id[policy_id]
            for policy_id in self._policy_ids_by_principal.get(principal, [])
            if self._policies_by_id[policy_id].enabled
        ]

    def _resolve(self, policy_id: str) -> ExecutionSecretTrustPolicy:
        policy = self._policies_by_id.get(policy_id)

        if policy is None:
            raise ExecutionSecretTrustError(f"No policy is registered under policy ID {policy_id!r}.")

        return policy

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionSecretTrustError(f"Cannot use an empty or blank {field_name}.")
