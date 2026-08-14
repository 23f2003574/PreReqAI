from dataclasses import (
    replace,
)

from threading import (
    RLock,
)

from .execution_policy import (
    ExecutionPolicy,
)

from .execution_policy_error import (
    ExecutionPolicyError,
)


class ExecutionPolicyService:
    """
    Registers and maintains reusable policies defining what an
    execution session is permitted to do.

    The service's responsibility is policy bookkeeping only. It does
    not itself evaluate a session against a policy; a disabled
    policy is simply never eligible to be evaluated by a caller.

    Behavior:
    - register() rejects a policy whose policy_id is already
      registered
    - update() replaces a policy's rules, never its identity, and
      the version it replaces is preserved rather than discarded
    - disable() takes effect immediately and is itself preserved as
      a new version, never rewriting history

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self):
        self._policies_by_id = {}
        self._history_by_id = {}
        self._lock = RLock()

    def register(self, policy: ExecutionPolicy) -> ExecutionPolicy:
        """
        Register a policy.

        Raises:
            ExecutionPolicyError: If policy is not an
                ExecutionPolicy, or its policy ID is already
                registered
        """

        if not isinstance(policy, ExecutionPolicy):
            raise ExecutionPolicyError(
                "Cannot register an invalid policy: policy must be an ExecutionPolicy."
            )

        with self._lock:
            if policy.policy_id in self._policies_by_id:
                raise ExecutionPolicyError(f"Policy ID {policy.policy_id!r} is already registered.")

            self._policies_by_id[policy.policy_id] = policy
            self._history_by_id[policy.policy_id] = [policy]

            return policy

    def get(self, policy_id: str) -> ExecutionPolicy:
        """
        Look up a policy's current version.

        Raises:
            ExecutionPolicyError: If policy_id is None or blank, or
                no policy is registered under it
        """

        self._validate_id(policy_id, "policy ID")

        with self._lock:
            return self._resolve(policy_id)

    def update(self, policy_id: str, rules) -> ExecutionPolicy:
        """
        Replace a policy's rules, preserving the version it replaces.

        Raises:
            ExecutionPolicyError: If policy_id is None or blank, no
                policy is registered under it, or rules is empty
        """

        self._validate_id(policy_id, "policy ID")

        with self._lock:
            policy = self._resolve(policy_id)

            updated = replace(policy, rules=rules)
            self._policies_by_id[policy_id] = updated
            self._history_by_id[policy_id].append(updated)

            return updated

    def disable(self, policy_id: str) -> ExecutionPolicy:
        """
        Disable a registered policy, so it can never be evaluated.

        Raises:
            ExecutionPolicyError: If policy_id is None or blank, or
                no policy is registered under it
        """

        self._validate_id(policy_id, "policy ID")

        with self._lock:
            policy = self._resolve(policy_id)

            updated = replace(policy, enabled=False)
            self._policies_by_id[policy_id] = updated
            self._history_by_id[policy_id].append(updated)

            return updated

    def list(self) -> list:
        """
        List every registered policy's current version.
        """

        with self._lock:
            return list(self._policies_by_id.values())

    def history(self, policy_id: str) -> list:
        """
        List every version of a policy, oldest first, including
        versions produced by update() and disable().

        Raises:
            ExecutionPolicyError: If policy_id is None or blank, or
                no policy is registered under it
        """

        self._validate_id(policy_id, "policy ID")

        with self._lock:
            self._resolve(policy_id)

            return list(self._history_by_id[policy_id])

    def _resolve(self, policy_id: str) -> ExecutionPolicy:
        policy = self._policies_by_id.get(policy_id)

        if policy is None:
            raise ExecutionPolicyError(f"No policy is registered under policy ID {policy_id!r}.")

        return policy

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionPolicyError(f"Cannot use an empty or blank {field_name}.")
