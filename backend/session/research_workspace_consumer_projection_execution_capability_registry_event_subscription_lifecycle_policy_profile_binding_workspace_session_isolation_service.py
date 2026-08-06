from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_isolation_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionIsolationError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_isolation_policy import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionIsolationPolicy,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_isolation_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionIsolationResult,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionIsolationService:
    """
    Enforces a single isolation policy across every consumer
    projection execution capability registry event subscription
    lifecycle policy profile binding workspace execution session, so
    concurrent sessions cannot access or modify each other's runtime
    state except through an explicit shared-resource grant.

    The service's responsibility is tracking and validating resource
    access, not the resources themselves. It does NOT allocate,
    provision, or otherwise touch whatever a resource identifier
    refers to; a caller is expected to call validate() immediately
    before a resource operation and decline to perform it when the
    returned result is not isolated.

    Behavior:
    - Every resource listed in the policy's shared_resources is
      accessible to every session without an explicit grant
    - Under isolation_level "STRICT", grant() denies granting a
      resource outside shared_resources to a session while it is
      already granted to a different session
    - Under isolation_level "SHARED", grant() places no such
      restriction: any resource may be granted to any number of
      sessions
    - revoke() removes a single explicit grant; it does not affect
      access derived from shared_resources

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(
        self,
        policy: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionIsolationPolicy,
    ):
        """
        Args:
            policy: The isolation policy enforced across every session
        """

        self._policy = policy
        self._grants_by_session_id = {}
        self._lock = RLock()

    def validate(
        self, session_id: str
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionIsolationResult:
        """
        Check a session's current resource access against the
        isolation policy, immediately before a resource operation.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionIsolationError:
                If session_id is None or blank
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            if self._policy.isolation_level != "STRICT":
                return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionIsolationResult(
                    isolated=True,
                    violations=(),
                )

            private_grants = self._grants_by_session_id.get(session_id, set()) - set(self._policy.shared_resources)

            violations = tuple(
                sorted(
                    resource
                    for resource in private_grants
                    if any(
                        resource in grants
                        for other_session_id, grants in self._grants_by_session_id.items()
                        if other_session_id != session_id
                    )
                )
            )

            if violations:
                return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionIsolationResult(
                    isolated=False,
                    violations=violations,
                )

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionIsolationResult(
                isolated=True,
                violations=(),
            )

    def grant(self, session_id: str, resource: str) -> None:
        """
        Grant a session explicit access to a resource.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionIsolationError:
                If session_id or resource is None or blank, or the
                policy's isolation_level is "STRICT", resource is
                outside shared_resources, and resource is already
                granted to a different session
        """

        self._validate_id(session_id, "session ID")
        self._validate_id(resource, "resource")

        with self._lock:
            if (
                self._policy.isolation_level == "STRICT"
                and resource not in self._policy.shared_resources
            ):
                for other_session_id, grants in self._grants_by_session_id.items():
                    if other_session_id != session_id and resource in grants:
                        raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionIsolationError(
                            f"Cannot grant resource {resource!r} to session ID {session_id!r}: it is already "
                            f"granted to session ID {other_session_id!r}."
                        )

            self._grants_by_session_id.setdefault(session_id, set()).add(resource)

    def revoke(self, session_id: str, resource: str) -> None:
        """
        Revoke a session's explicit access to a resource.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionIsolationError:
                If session_id or resource is None or blank, or
                resource is not currently granted to session_id
        """

        self._validate_id(session_id, "session ID")
        self._validate_id(resource, "resource")

        with self._lock:
            grants = self._grants_by_session_id.get(session_id, set())

            if resource not in grants:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionIsolationError(
                    f"Resource {resource!r} is not granted to session ID {session_id!r}."
                )

            grants.discard(resource)

    def accessible(self, session_id: str) -> tuple:
        """
        List every resource a session may currently access, whether
        through the policy's shared_resources or an explicit grant.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionIsolationError:
                If session_id is None or blank
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            granted = self._grants_by_session_id.get(session_id, set())

            return tuple(sorted(set(self._policy.shared_resources) | granted))

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionIsolationError(
                f"Cannot operate with an empty or blank {label}."
            )
