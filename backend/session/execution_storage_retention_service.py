from dataclasses import (
    replace,
)

from threading import (
    RLock,
)

from uuid import uuid4

from .execution_storage_garbage_record import (
    RESOURCE_REPLICA,
    RESOURCE_SNAPSHOT,
    RESOURCE_TYPES,
    RESOURCE_VOLUME,
)

from .execution_storage_retention_policy import (
    ExecutionStorageRetentionPolicy,
)

from .execution_storage_retention_policy_error import (
    ExecutionStorageRetentionPolicyError,
)


class ExecutionStorageRetentionService:
    """
    Defines how long execution storage resources remain available
    before becoming eligible for garbage collection.

    Composes with:
    - an existing storage garbage collection service (anything
      exposing `protected(resource_id) -> bool`, matching
      ExecutionStorageGarbageCollectionService), used as the single
      source of truth for whether a resource is currently active or
      attached
    - an existing storage volume service (anything exposing
      `status(volume_id) -> str` and `scope_of(volume_id) -> str`,
      the former matching ExecutionStorageVolumeService), used to
      classify a bare resource ID and resolve its scope
    - an existing storage snapshot service (anything exposing
      `get(snapshot_id) -> object with .volume_id`, matching
      ExecutionStorageSnapshotService)
    - an existing storage replication service (anything exposing
      `get(replica_id) -> object with .volume_id`)

    Behavior:
    - configure() replaces the enabled policy for a scope/resource
      type pair with a freshly built one
    - eligible() reports whether a resource currently qualifies for
      automatic collection: never true for an active or attached
      resource, and never true when no enabled policy covers its
      scope and resource type
    - policy() reports the policy configured for a scope/resource
      type pair
    - disable() turns off an existing policy, preventing it from
      permitting further automatic collection

    Policies are isolated per (scope_id, resource_type) pair.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, gc_service, volume_service, snapshot_service, replica_service):
        self._gc_service = gc_service
        self._volume_service = volume_service
        self._snapshot_service = snapshot_service
        self._replica_service = replica_service
        self._policies_by_key = {}
        self._policies_by_id = {}
        self._lock = RLock()

    def configure(
        self, scope_id: str, resource_type: str, retention_seconds: float
    ) -> ExecutionStorageRetentionPolicy:
        """
        Replace the policy for (scope_id, resource_type) with a
        freshly built, enabled one.

        Raises:
            ExecutionStorageRetentionPolicyError: If scope_id is None
                or blank, resource_type is not one of RESOURCE_TYPES,
                or retention_seconds is not a positive number
        """

        self._validate_text(scope_id, "scope ID")
        self._validate_resource_type(resource_type)

        policy = ExecutionStorageRetentionPolicy(
            policy_id=str(uuid4()),
            scope_id=scope_id,
            resource_type=resource_type,
            retention_seconds=retention_seconds,
            enabled=True,
        )

        with self._lock:
            self._policies_by_key[(scope_id, resource_type)] = policy
            self._policies_by_id[policy.policy_id] = policy

        return policy

    def eligible(self, resource_id: str) -> bool:
        """
        Whether resource_id currently qualifies for automatic
        collection.

        Raises:
            ExecutionStorageRetentionPolicyError: If resource_id is
                None or blank, or it is unknown
        """

        self._validate_text(resource_id, "resource ID")

        if self._safe_call(self._gc_service.protected, resource_id):
            return False

        resource_type, volume_id = self._classify(resource_id)
        scope_id = self._safe_call(self._volume_service.scope_of, volume_id)

        with self._lock:
            policy = self._policies_by_key.get((scope_id, resource_type))

        return policy is not None and policy.enabled

    def policy(self, scope_id: str, resource_type: str) -> ExecutionStorageRetentionPolicy:
        """
        The policy configured for (scope_id, resource_type).

        Raises:
            ExecutionStorageRetentionPolicyError: If scope_id is None
                or blank, resource_type is not one of RESOURCE_TYPES,
                or no policy is configured for the pair
        """

        self._validate_text(scope_id, "scope ID")
        self._validate_resource_type(resource_type)

        with self._lock:
            policy = self._policies_by_key.get((scope_id, resource_type))

        if policy is None:
            raise ExecutionStorageRetentionPolicyError(
                f"No retention policy is configured for scope ID {scope_id!r} and resource "
                f"type {resource_type!r}."
            )

        return policy

    def disable(self, policy_id: str) -> ExecutionStorageRetentionPolicy:
        """
        Disable an existing policy, preventing it from permitting
        further automatic collection. Idempotent: disabling an
        already-disabled policy simply returns it unchanged.

        Raises:
            ExecutionStorageRetentionPolicyError: If policy_id is None
                or blank, or no policy is registered under it
        """

        self._validate_text(policy_id, "policy ID")

        with self._lock:
            policy = self._policies_by_id.get(policy_id)

            if policy is None:
                raise ExecutionStorageRetentionPolicyError(
                    f"No retention policy is registered under policy ID {policy_id!r}."
                )

            if not policy.enabled:
                return policy

            disabled = replace(policy, enabled=False)
            self._policies_by_id[policy_id] = disabled
            self._policies_by_key[(policy.scope_id, policy.resource_type)] = disabled

            return disabled

    def _classify(self, resource_id: str):
        try:
            self._volume_service.status(resource_id)

            return RESOURCE_VOLUME, resource_id
        except Exception:
            pass

        try:
            snapshot = self._snapshot_service.get(resource_id)

            return RESOURCE_SNAPSHOT, snapshot.volume_id
        except Exception:
            pass

        try:
            replica = self._replica_service.get(resource_id)

            return RESOURCE_REPLICA, replica.volume_id
        except Exception:
            pass

        raise ExecutionStorageRetentionPolicyError(
            f"Cannot resolve resource ID {resource_id!r}: it is unknown."
        )

    @staticmethod
    def _safe_call(fn, *args):
        try:
            return fn(*args)
        except Exception as error:
            raise ExecutionStorageRetentionPolicyError(f"Cannot resolve: {error}") from error

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionStorageRetentionPolicyError(f"Cannot use an empty or blank {field_name}.")

    @staticmethod
    def _validate_resource_type(resource_type: str) -> None:
        if resource_type not in RESOURCE_TYPES:
            raise ExecutionStorageRetentionPolicyError(
                f"Cannot use an unknown resource_type: {resource_type!r}."
            )
