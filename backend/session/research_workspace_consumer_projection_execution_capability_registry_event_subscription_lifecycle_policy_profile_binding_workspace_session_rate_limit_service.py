from datetime import (
    datetime,
    timedelta,
    timezone,
)

from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_rate_limit_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionRateLimitError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_rate_limit import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionRateLimit,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_rate_limit_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionRateLimitResult,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionRateLimitService:
    """
    Enforces configurable, per-operation sliding-window rate limits on
    a consumer projection execution capability registry event
    subscription lifecycle policy profile binding workspace execution
    session's lifecycle operations, so a single session cannot invoke
    an operation more often than its configured limit allows.

    The service's responsibility is counting and enforcing requests
    against configured limits, not performing the lifecycle
    operations themselves. A caller is expected to call check()
    immediately before a lifecycle operation and decline to perform
    it when the result is not allowed, then call record() once the
    operation actually runs.

    Behavior:
    - Counters are tracked independently per (session_id, operation)
      pair; one session's request history never affects another
      session's quota, even for the same operation
    - The window is a true sliding window: a request counts against
      the limit only until window_seconds have elapsed since it was
      recorded, at which point it ages out on its own the next time
      that (session_id, operation) pair is checked, recorded, or
      queried
    - check() previews the current decision without recording a
      request; record() records one and returns the resulting
      decision
    - reset() clears every counter held for a session, across every
      operation

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, limits=()):
        """
        Args:
            limits: The ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionRateLimit
                instances to register upfront, keyed by their
                operation

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionRateLimitError:
                If two given limits share an operation
        """

        self._limit_by_operation = {}
        self._timestamps = {}
        self._lock = RLock()

        for limit in limits:
            if limit.operation in self._limit_by_operation:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionRateLimitError(
                    f"Operation {limit.operation!r} already has a rate limit registered."
                )

            self._limit_by_operation[limit.operation] = limit

    def check(
        self, session_id: str, operation: str
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionRateLimitResult:
        """
        Preview whether a session may currently invoke an operation,
        without recording a request.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionRateLimitError:
                If session_id or operation is None or blank, or no
                rate limit is registered for operation
        """

        self._validate_id(session_id, "session ID")
        limit = self._resolve_limit(operation)

        with self._lock:
            timestamps = self._prune(session_id, operation, limit)
            count = len(timestamps)

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionRateLimitResult(
                allowed=count < limit.max_requests,
                remaining=max(0, limit.max_requests - count),
                reset_at=self._reset_at(timestamps, limit),
            )

    def record(
        self, session_id: str, operation: str
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionRateLimitResult:
        """
        Record a request for an operation against a session's quota,
        counting it only if the session is currently within its
        limit.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionRateLimitError:
                If session_id or operation is None or blank, or no
                rate limit is registered for operation
        """

        self._validate_id(session_id, "session ID")
        limit = self._resolve_limit(operation)

        with self._lock:
            timestamps = self._prune(session_id, operation, limit)
            count = len(timestamps)

            if count >= limit.max_requests:
                return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionRateLimitResult(
                    allowed=False,
                    remaining=0,
                    reset_at=self._reset_at(timestamps, limit),
                )

            timestamps.append(datetime.now(timezone.utc))
            self._timestamps[(session_id, operation)] = timestamps

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionRateLimitResult(
                allowed=True,
                remaining=max(0, limit.max_requests - len(timestamps)),
                reset_at=self._reset_at(timestamps, limit),
            )

    def remaining(self, session_id: str, operation: str) -> int:
        """
        Report how many further requests a session may currently make
        for an operation within its sliding window.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionRateLimitError:
                If session_id or operation is None or blank, or no
                rate limit is registered for operation
        """

        self._validate_id(session_id, "session ID")
        limit = self._resolve_limit(operation)

        with self._lock:
            timestamps = self._prune(session_id, operation, limit)

            return max(0, limit.max_requests - len(timestamps))

    def reset(self, session_id: str) -> None:
        """
        Clear every rate limit counter held for a session, across
        every operation.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionRateLimitError:
                If session_id is None or blank
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            for key in [key for key in self._timestamps if key[0] == session_id]:
                del self._timestamps[key]

    def _prune(self, session_id: str, operation: str, limit) -> list:
        key = (session_id, operation)
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=limit.window_seconds)
        kept = [timestamp for timestamp in self._timestamps.get(key, []) if timestamp > cutoff]

        self._timestamps[key] = kept

        return kept

    def _reset_at(self, timestamps: list, limit) -> datetime:
        if timestamps:
            return timestamps[0] + timedelta(seconds=limit.window_seconds)

        return datetime.now(timezone.utc) + timedelta(seconds=limit.window_seconds)

    def _resolve_limit(
        self, operation: str
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionRateLimit:
        if operation is None or not isinstance(operation, str) or not operation.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionRateLimitError(
                "Cannot operate with an empty, blank, or non-string operation."
            )

        limit = self._limit_by_operation.get(operation)

        if limit is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionRateLimitError(
                f"No rate limit is registered for operation {operation!r}."
            )

        return limit

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionRateLimitError(
                f"Cannot operate with an empty or blank {label}."
            )
