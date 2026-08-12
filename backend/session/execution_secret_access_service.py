from threading import (
    RLock,
)

from uuid import uuid4

from .execution_secret_access_error import (
    ExecutionSecretAccessError,
)

from .execution_secret_operation import (
    ExecutionSecretOperation,
)

from .execution_secret_policy import (
    ExecutionSecretPolicy,
)


class ExecutionSecretAccessService:
    """
    Controls which execution components may access specific secrets,
    by granting and revoking policies that each permit one principal
    a specific set of operations against one secret.

    The service's responsibility is policy bookkeeping and
    authorization checks only. It does not store or resolve secret
    values itself; it relies on an existing execution secret registry
    only for secret IDs to scope policies against.

    Behavior:
    - A secret may have any number of policies, including several for
      the same principal
    - authorize() defaults to deny: it only returns True when at
      least one enabled policy for the secret and principal grants
      the requested operation
    - A disabled policy never authorizes anything, regardless of
      which operations it lists
    - revoke() takes effect immediately: a subsequent authorize()
      call no longer considers the revoked policy

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self):
        self._policies_by_id = {}
        self._policy_ids_by_secret = {}
        self._lock = RLock()

    def grant(
        self,
        secret_id: str,
        principal: str,
        operations,
        enabled: bool = True,
    ) -> ExecutionSecretPolicy:
        """
        Grant a principal a set of operations against a secret.

        Raises:
            ExecutionSecretAccessError: If secret_id or principal is
                None or blank, operations is empty or contains an
                operation not in ExecutionSecretOperation, or enabled
                is not a bool
        """

        self._validate_id(secret_id, "secret ID")
        self._validate_id(principal, "principal")

        policy = ExecutionSecretPolicy(
            policy_id=str(uuid4()),
            secret_id=secret_id,
            principal=principal,
            operations=operations,
            enabled=enabled,
        )

        with self._lock:
            self._policies_by_id[policy.policy_id] = policy
            self._policy_ids_by_secret.setdefault(secret_id, []).append(policy.policy_id)

            return policy

    def revoke(self, policy_id: str) -> ExecutionSecretPolicy:
        """
        Revoke a granted policy, taking effect immediately.

        Raises:
            ExecutionSecretAccessError: If policy_id is None or
                blank, or no policy is registered under it
        """

        self._validate_id(policy_id, "policy ID")

        with self._lock:
            policy = self._resolve(policy_id)

            del self._policies_by_id[policy_id]
            self._policy_ids_by_secret[policy.secret_id].remove(policy_id)

            return policy

    def authorize(self, secret_id: str, principal: str, operation) -> bool:
        """
        Check whether a principal is currently authorized to perform
        an operation against a secret.

        Defaults to deny: returns False unless at least one enabled
        policy for the secret and principal grants the operation.

        Raises:
            ExecutionSecretAccessError: If secret_id or principal is
                None or blank, or operation is not a valid
                ExecutionSecretOperation
        """

        self._validate_id(secret_id, "secret ID")
        self._validate_id(principal, "principal")

        try:
            normalized_operation = ExecutionSecretOperation(operation)
        except ValueError as error:
            raise ExecutionSecretAccessError(f"Invalid operation {operation!r}.") from error

        with self._lock:
            for policy in self._policies(secret_id):
                if (
                    policy.enabled
                    and policy.principal == principal
                    and normalized_operation in policy.operations
                ):
                    return True

            return False

    def policies(self, secret_id: str) -> list:
        """
        List every currently granted policy for a secret, in the
        order they were granted.

        Raises:
            ExecutionSecretAccessError: If secret_id is None or blank
        """

        self._validate_id(secret_id, "secret ID")

        with self._lock:
            return self._policies(secret_id)

    def _policies(self, secret_id: str) -> list:
        return [
            self._policies_by_id[policy_id]
            for policy_id in self._policy_ids_by_secret.get(secret_id, [])
        ]

    def _resolve(self, policy_id: str) -> ExecutionSecretPolicy:
        policy = self._policies_by_id.get(policy_id)

        if policy is None:
            raise ExecutionSecretAccessError(f"No policy is registered under policy ID {policy_id!r}.")

        return policy

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionSecretAccessError(f"Cannot use an empty or blank {field_name}.")
