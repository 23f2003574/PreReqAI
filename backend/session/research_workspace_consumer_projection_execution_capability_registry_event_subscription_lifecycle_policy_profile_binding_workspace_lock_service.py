from datetime import (
    datetime,
    timedelta,
    timezone,
)

from threading import (
    RLock,
)

from uuid import uuid4

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_lock_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceLockError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_resource_lock import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceResourceLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_lock_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceLockResult,
)

_DEFAULT_TTL_SECONDS = 300


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceLockService:
    """
    Grants consumer projection execution capability registry event
    subscription lifecycle policy profile binding workspace execution
    pipelines exclusive, automatically expiring access to workspace
    resources, so two pipelines can never hold the same resource at
    once.

    The service's responsibility is lock bookkeeping, not running a
    pipeline itself. It does NOT execute pipelines; whoever runs one
    (for example, a consumer projection execution capability registry
    event subscription lifecycle policy profile binding workspace
    execution pipeline service, by way of a pipeline queue service)
    is expected to call acquire() for every resource a stage is about
    to modify, and release() for each lock it was granted once the
    pipeline finishes.

    Behavior:
    - A resource identified by (resource_type, resource_id) may have
      at most one active lock at a time
    - acquire() is idempotent for the pipeline that already holds a
      resource's active lock: it returns that same lock again rather
      than being refused
    - A lock past its expires_at is treated as inactive by acquire()
      and is_locked(), even before cleanup_expired() physically
      removes it
    - Refusal (an already actively locked resource held by a
      different pipeline) is reported through the returned result
      rather than raised, since contention is an expected outcome,
      not a validation failure

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self):
        self._locks = {}
        self._lock = RLock()

    def acquire(
        self,
        resource_type: str,
        resource_id: str,
        pipeline_id: str,
        ttl_seconds: float = _DEFAULT_TTL_SECONDS,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceLockResult:
        """
        Attempt to acquire exclusive access to a resource.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceLockError:
                If resource_type, resource_id, or pipeline_id is None
                or blank, or ttl_seconds is not a positive number
        """

        self._validate_id(resource_type, "resource type")
        self._validate_id(resource_id, "resource ID")
        self._validate_id(pipeline_id, "pipeline ID")

        if ttl_seconds is None or isinstance(ttl_seconds, bool) or not isinstance(ttl_seconds, (int, float)):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceLockError(
                "Cannot acquire a workspace resource lock with a non-numeric ttl_seconds."
            )

        if ttl_seconds <= 0:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceLockError(
                f"Cannot acquire a workspace resource lock with ttl_seconds {ttl_seconds!r}; ttl_seconds "
                "must be greater than zero."
            )

        key = (resource_type, resource_id)

        with self._lock:
            existing = self._active_lock(key)

            if existing is not None:
                if existing.pipeline_id == pipeline_id:
                    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceLockResult(
                        acquired=True,
                        reason="Lock already held by this pipeline.",
                        lock=existing,
                    )

                return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceLockResult(
                    acquired=False,
                    reason=(
                        f"Resource type {resource_type!r} ID {resource_id!r} is locked by pipeline ID "
                        f"{existing.pipeline_id!r} until {existing.expires_at.isoformat()}."
                    ),
                    lock=None,
                )

            now = datetime.now(timezone.utc)

            lock = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceResourceLock(
                lock_id=str(uuid4()),
                resource_type=resource_type,
                resource_id=resource_id,
                pipeline_id=pipeline_id,
                acquired_at=now,
                expires_at=now + timedelta(seconds=ttl_seconds),
            )

            self._locks[key] = lock

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceLockResult(
                acquired=True,
                reason="Lock acquired.",
                lock=lock,
            )

    def release(self, lock_id: str) -> None:
        """
        Release a held lock.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceLockError:
                If lock_id is None or blank, or no active lock is
                registered under it
        """

        self._validate_id(lock_id, "lock ID")

        with self._lock:
            key = self._find_key_by_lock_id(lock_id)

            if key is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceLockError(
                    f"No active workspace resource lock is registered under lock ID {lock_id!r}."
                )

            del self._locks[key]

    def is_locked(self, resource_type: str, resource_id: str) -> bool:
        """
        Check whether a resource currently has an active lock.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceLockError:
                If resource_type or resource_id is None or blank
        """

        self._validate_id(resource_type, "resource type")
        self._validate_id(resource_id, "resource ID")

        with self._lock:
            return self._active_lock((resource_type, resource_id)) is not None

    def locks(self, pipeline_id: str) -> tuple:
        """
        List every currently active lock held by a pipeline.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceLockError:
                If pipeline_id is None or blank
        """

        self._validate_id(pipeline_id, "pipeline ID")

        now = datetime.now(timezone.utc)

        with self._lock:
            return tuple(
                lock
                for lock in self._locks.values()
                if lock.pipeline_id == pipeline_id and lock.expires_at > now
            )

    def cleanup_expired(self) -> int:
        """
        Physically remove every lock whose expiration has passed.

        Returns:
            The number of locks removed
        """

        now = datetime.now(timezone.utc)

        with self._lock:
            expired_keys = [key for key, lock in self._locks.items() if lock.expires_at <= now]

            for key in expired_keys:
                del self._locks[key]

            return len(expired_keys)

    def _active_lock(self, key):
        lock = self._locks.get(key)

        if lock is None:
            return None

        if lock.expires_at <= datetime.now(timezone.utc):
            return None

        return lock

    def _find_key_by_lock_id(self, lock_id: str):
        now = datetime.now(timezone.utc)

        for key, lock in self._locks.items():
            if lock.lock_id == lock_id and lock.expires_at > now:
                return key

        return None

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceLockError(
                f"Cannot operate with an empty or blank {label}."
            )
