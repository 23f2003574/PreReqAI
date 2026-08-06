from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_resource_governance_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionResourceGovernanceError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_resource_usage import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionResourceUsage,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionResourceGovernanceService:
    """
    Allocates CPU, memory, and storage to a consumer projection
    execution capability registry event subscription lifecycle policy
    profile binding workspace execution session according to its
    assigned session policy's resource limits, out of a fixed,
    cluster-wide capacity shared by every session, so no combination
    of concurrently running sessions can consume more than the
    cluster actually has.

    The service's responsibility is allocation bookkeeping, not
    provisioning real CPU, memory, or storage itself. It does NOT
    define what a session's assigned policy is; it relies on the
    existing session policy service, given at construction time, only
    to resolve which resource policy governs a session.

    Behavior:
    - A session may hold at most one active allocation at a time;
      allocating for a session that already has one active is
      rejected
    - allocate() reserves a session's resource policy limits in full;
      it is rejected outright if those limits alone exceed the
      service's total capacity, and rejected as an over-allocation if
      adding them to every other currently active allocation would
      exceed that capacity
    - release() frees an allocation's reservation entirely

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(
        self,
        policy_service,
        resource_policies=(),
        cpu_capacity: float = None,
        memory_capacity: float = None,
        storage_capacity: float = None,
    ):
        """
        Args:
            policy_service: The service used to resolve which session
                policy governs a session. Any object exposing
                `policy(session_id)`, raising if the session has no
                assigned policy, is accepted
            resource_policies: The
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionResourcePolicy
                instances to register upfront, keyed by their
                policy_id
            cpu_capacity: The total CPU available across every
                concurrently active allocation
            memory_capacity: The total memory available across every
                concurrently active allocation
            storage_capacity: The total storage available across
                every concurrently active allocation

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionResourceGovernanceError:
                If two given resource policies share a policy_id, or
                cpu_capacity, memory_capacity, or storage_capacity is
                not a positive number
        """

        for value, label in (
            (cpu_capacity, "cpu_capacity"),
            (memory_capacity, "memory_capacity"),
            (storage_capacity, "storage_capacity"),
        ):
            if value is None or isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionResourceGovernanceError(
                    f"Invalid {label} {value!r}; {label} must be a positive number."
                )

        self._policy_service = policy_service
        self._resource_policies_by_id = {}
        self._cpu_capacity = cpu_capacity
        self._memory_capacity = memory_capacity
        self._storage_capacity = storage_capacity
        self._usage_by_session_id = {}
        self._lock = RLock()

        for resource_policy in resource_policies:
            if resource_policy.policy_id in self._resource_policies_by_id:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionResourceGovernanceError(
                    f"Resource policy ID {resource_policy.policy_id!r} is already registered."
                )

            self._resource_policies_by_id[resource_policy.policy_id] = resource_policy

    def allocate(
        self, session_id: str
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionResourceUsage:
        """
        Reserve a session's assigned resource policy limits, in full,
        immediately before it executes.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionResourceGovernanceError:
                If session_id is None or blank, session_id already has
                an active allocation, the session has no assigned
                policy, no resource policy is registered for that
                policy's ID, or reserving that policy's limits would
                exceed the service's total capacity
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            if session_id in self._usage_by_session_id:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionResourceGovernanceError(
                    f"Session ID {session_id!r} already has an active resource allocation."
                )

            resource_policy = self._resolve_resource_policy(session_id)
            cpu_total, memory_total, storage_total = self._current_totals()

            if (
                cpu_total + resource_policy.cpu_limit > self._cpu_capacity
                or memory_total + resource_policy.memory_limit > self._memory_capacity
                or storage_total + resource_policy.storage_limit > self._storage_capacity
            ):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionResourceGovernanceError(
                    f"Cannot allocate resources for session ID {session_id!r}: reserving policy ID "
                    f"{resource_policy.policy_id!r} would exceed available capacity."
                )

            usage = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionResourceUsage(
                session_id=session_id,
                cpu_used=resource_policy.cpu_limit,
                memory_used=resource_policy.memory_limit,
                storage_used=resource_policy.storage_limit,
            )

            self._usage_by_session_id[session_id] = usage

            return usage

    def release(self, session_id: str) -> None:
        """
        Free a session's active resource allocation, on completion or
        cancellation.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionResourceGovernanceError:
                If session_id is None or blank, or session_id has no
                active allocation
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            self._resolve_usage(session_id)

            del self._usage_by_session_id[session_id]

    def usage(
        self, session_id: str
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionResourceUsage:
        """
        Report a session's currently allocated resource usage.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionResourceGovernanceError:
                If session_id is None or blank, or session_id has no
                active allocation
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            return self._resolve_usage(session_id)

    def validate(self, session_id: str) -> bool:
        """
        Confirm a session's currently allocated usage is within its
        assigned resource policy's limits.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionResourceGovernanceError:
                If session_id is None or blank, session_id has no
                active allocation, the session has no assigned policy,
                no resource policy is registered for that policy's
                ID, or usage exceeds any of that policy's limits
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            usage = self._resolve_usage(session_id)
            resource_policy = self._resolve_resource_policy(session_id)

            if (
                usage.cpu_used > resource_policy.cpu_limit
                or usage.memory_used > resource_policy.memory_limit
                or usage.storage_used > resource_policy.storage_limit
            ):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionResourceGovernanceError(
                    f"Session ID {session_id!r} usage exceeds policy ID {resource_policy.policy_id!r} limits."
                )

            return True

    def _current_totals(self) -> tuple:
        cpu_total = sum(usage.cpu_used for usage in self._usage_by_session_id.values())
        memory_total = sum(usage.memory_used for usage in self._usage_by_session_id.values())
        storage_total = sum(usage.storage_used for usage in self._usage_by_session_id.values())

        return cpu_total, memory_total, storage_total

    def _resolve_resource_policy(self, session_id: str):
        try:
            policy = self._policy_service.policy(session_id)
        except Exception as error:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionResourceGovernanceError(
                f"Session ID {session_id!r} has no assigned session policy."
            ) from error

        resource_policy = self._resource_policies_by_id.get(policy.policy_id)

        if resource_policy is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionResourceGovernanceError(
                f"No resource policy is registered for policy ID {policy.policy_id!r}."
            )

        return resource_policy

    def _resolve_usage(
        self, session_id: str
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionResourceUsage:
        usage = self._usage_by_session_id.get(session_id)

        if usage is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionResourceGovernanceError(
                f"Session ID {session_id!r} has no active resource allocation."
            )

        return usage

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionResourceGovernanceError(
                f"Cannot operate with an empty or blank {label}."
            )
