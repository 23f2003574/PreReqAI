from dataclasses import (
    replace,
)

from threading import (
    RLock,
)

from .execution_recovery_conflict_policy_error import (
    ExecutionRecoveryConflictPolicyError,
)

from .execution_recovery_conflict_policy import (
    ExecutionRecoveryConflictPolicy,
)


class ExecutionRecoveryConflictPolicyService:
    """
    Applies reusable, per-field policies to automatically resolve
    recovery conflicts.

    Conflicts are assumed to already exist elsewhere; this service
    depends on plain resolver callables for them rather than a
    concrete store:
    - conflict_resolver(conflict_id) -> conflict or None
    - record_resolution(conflict_id, resolution) -> the resolved
      conflict; matches the signature of an execution recovery
      conflict service's resolve() method

    Behavior:
    - register() adds a policy for its field
    - resolve() applies the matching enabled policy with the
      highest precedence to a conflict, recording CHECKPOINT or
      CURRENT via record_resolution(); a REJECT policy instead
      raises, flagging the conflict for manual attention; if no
      enabled policy matches, the conflict is left unresolved and
      None is returned
    - policies() lists every policy registered for a field,
      regardless of enabled state, in registration order
    - disable() turns a policy off; a disabled policy is never
      applied

    When more than one enabled policy matches a field, the most
    recently registered one takes precedence.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, conflict_resolver, record_resolution):
        self._conflict_resolver = conflict_resolver
        self._record_resolution = record_resolution
        self._policies_by_id = {}
        self._policy_ids_by_field = {}
        self._lock = RLock()

    def register(self, policy: ExecutionRecoveryConflictPolicy) -> ExecutionRecoveryConflictPolicy:
        """
        Add a policy for its field.

        Raises:
            ExecutionRecoveryConflictPolicyError: If policy is not
                an ExecutionRecoveryConflictPolicy, or its policy_id
                is already registered
        """

        if not isinstance(policy, ExecutionRecoveryConflictPolicy):
            raise ExecutionRecoveryConflictPolicyError(
                "Cannot register a policy that is not an ExecutionRecoveryConflictPolicy."
            )

        with self._lock:
            if policy.policy_id in self._policies_by_id:
                raise ExecutionRecoveryConflictPolicyError(
                    f"Policy ID {policy.policy_id!r} is already registered."
                )

            self._policies_by_id[policy.policy_id] = policy
            self._policy_ids_by_field.setdefault(policy.field, []).append(policy.policy_id)

            return policy

    def resolve(self, conflict_id: str):
        """
        Apply the matching enabled policy with the highest
        precedence to a conflict.

        Raises:
            ExecutionRecoveryConflictPolicyError: If conflict_id is
                None or blank, no conflict is known under it, or the
                winning policy is REJECT
        """

        self._validate_id(conflict_id, "conflict ID")

        with self._lock:
            conflict = self._conflict_resolver(conflict_id)

            if conflict is None:
                raise ExecutionRecoveryConflictPolicyError(f"No conflict is known under conflict ID {conflict_id!r}.")

            winning_policy = self._winning_policy(conflict.field)

            if winning_policy is None:
                return None

            if winning_policy.resolution == "REJECT":
                raise ExecutionRecoveryConflictPolicyError(
                    f"Conflict ID {conflict_id!r} matches a REJECT policy for field {conflict.field!r}; it "
                    "cannot be auto-resolved."
                )

            return self._record_resolution(conflict_id, winning_policy.resolution)

    def policies(self, field: str) -> tuple:
        """
        List every policy registered for a field, regardless of
        enabled state, in registration order.

        Raises:
            ExecutionRecoveryConflictPolicyError: If field is None
                or blank
        """

        self._validate_id(field, "field")

        with self._lock:
            return tuple(
                self._policies_by_id[policy_id] for policy_id in self._policy_ids_by_field.get(field, [])
            )

    def disable(self, policy_id: str) -> None:
        """
        Turn a policy off, so it is never applied again.

        Raises:
            ExecutionRecoveryConflictPolicyError: If policy_id is
                None or blank, or no policy is known under it
        """

        self._validate_id(policy_id, "policy ID")

        with self._lock:
            policy = self._policies_by_id.get(policy_id)

            if policy is None:
                raise ExecutionRecoveryConflictPolicyError(f"No policy is known under policy ID {policy_id!r}.")

            if policy.enabled:
                self._policies_by_id[policy_id] = replace(policy, enabled=False)

    def _winning_policy(self, field: str) -> ExecutionRecoveryConflictPolicy | None:
        enabled_policies = [
            self._policies_by_id[policy_id]
            for policy_id in self._policy_ids_by_field.get(field, [])
            if self._policies_by_id[policy_id].enabled
        ]

        return enabled_policies[-1] if enabled_policies else None

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionRecoveryConflictPolicyError(f"Cannot use an empty or blank {field_name}.")
