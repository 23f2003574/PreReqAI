from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_group_deployment_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_group_deployment_request import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentRequest,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_group_deployment_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_state import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingState,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentService:
    """
    Atomically deploys a published, currently released version of a
    consumer projection execution capability registry event
    subscription lifecycle policy profile binding group into a
    target runtime environment, so every member binding is deployed
    together as a single, consistent unit.

    The service's responsibility is orchestrating deployment, not
    group creation, membership management, version publication, or
    activation themselves. It does NOT create groups, mutate group
    membership, publish or roll back versions, activate or
    deactivate bindings, persist results, log, or publish events.

    The service is:
    - Thread-safe: Active deployment bookkeeping is guarded by an
      internal lock
    - Conflict-aware: deploy() rejects a group that already has an
      active deployment; redeploy() replaces it atomically instead
    - Atomic: Every member binding is validated before any deployment
      is recorded, so a single invalid or inactive member fails the
      whole deployment, leaving no partial deployment in place
    - Released-only: Only the group's currently released (its version
      history's current) version may be deployed
    """

    def __init__(
        self,
        group_version_service,
        binding_registry,
        activation_service,
    ):
        """
        Args:
            group_version_service: The service used to resolve a
                published group version and verify it is currently
                released. Any object exposing `find(group_id,
                version)` and `latest(group_id)` is accepted
            binding_registry: The registry used to verify a member
                binding exists. Any object exposing `find(binding_id)`
                is accepted
            activation_service: The service used to verify a member
                binding is active. Any object exposing
                `state(binding_id)` is accepted
        """

        for dependency, name in (
            (group_version_service, "group version service"),
            (binding_registry, "binding registry"),
            (activation_service, "activation service"),
        ):
            if dependency is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentError(
                    f"Cannot initialize deployment service with a None {name}."
                )

        self._group_version_service = group_version_service
        self._binding_registry = binding_registry
        self._activation_service = activation_service
        self._active_deployments = {}
        self._lock = RLock()

    def deploy(
        self,
        request: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentRequest,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentResult:
        """
        Deploy a group's published version into its target
        environment.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentError:
                If the request is malformed, no such group version has
                been published, the version is not currently
                released, any member binding is unknown or not
                currently active, or the group already has an active
                deployment
        """

        self._validate_request(request)

        with self._lock:
            if request.group_id in self._active_deployments:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentError(
                    f"Cannot deploy: group ID {request.group_id!r} already has an active deployment."
                )

            return self._deploy_locked(
                request.group_id,
                request.version,
                f"deployment::{request.group_id}",
            )

    def redeploy(
        self,
        group_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentResult:
        """
        Atomically replace a group's current active deployment,
        re-resolving its currently released version.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentError:
                If the group ID is None or blank, no deployment is
                currently active for it, or its currently released
                version can no longer be deployed
        """

        self._validate_identifier(group_id, "group ID")

        with self._lock:
            existing = self._active_deployments.get(group_id)

            if existing is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentError(
                    f"Cannot redeploy: group ID {group_id!r} has no active deployment."
                )

            current = self._group_version_service.latest(group_id)

            return self._deploy_locked(group_id, current.version, existing.deployment_id)

    def undeploy(self, group_id: str) -> None:
        """
        Remove a group's active deployment.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentError:
                If the group ID is None or blank, or no deployment is
                currently active for it
        """

        self._validate_identifier(group_id, "group ID")

        with self._lock:
            if group_id not in self._active_deployments:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentError(
                    f"Cannot undeploy: group ID {group_id!r} has no active deployment."
                )

            del self._active_deployments[group_id]

    def deployment(self, group_id: str):
        """
        Look up a group's currently active deployment.

        Returns:
            The active deployment result for group_id, or None if it
            has no active deployment

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentError:
                If the group ID is None or blank
        """

        self._validate_identifier(group_id, "group ID")

        with self._lock:
            return self._active_deployments.get(group_id)

    def _deploy_locked(
        self,
        group_id: str,
        version: str,
        deployment_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentResult:
        snapshot = self._resolve_released_version(group_id, version)

        deployed_bindings = []

        for binding_id in snapshot.binding_ids:
            binding = self._binding_registry.find(binding_id)

            if binding is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentError(
                    f"Cannot deploy: no binding is registered under binding ID {binding_id!r}."
                )

            if self._activation_service.state(binding_id) != ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingState.ACTIVE:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentError(
                    f"Cannot deploy: binding ID {binding_id!r} is not currently active."
                )

            deployed_bindings.append(binding_id)

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentResult(
            deployment_id=deployment_id,
            deployed_bindings=tuple(deployed_bindings),
            successful=True,
        )

        self._active_deployments[group_id] = result

        return result

    def _resolve_released_version(self, group_id: str, version: str):
        snapshot = self._group_version_service.find(group_id, version)

        if snapshot is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentError(
                f"Cannot deploy: no version {version!r} has been published for group ID {group_id!r}."
            )

        current = self._group_version_service.latest(group_id)

        if current.version != version:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentError(
                f"Cannot deploy: version {version!r} is not the currently released version for group ID {group_id!r}."
            )

        return snapshot

    def _validate_identifier(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentError(
                f"Cannot operate with an empty or blank {label}."
            )

    def _validate_request(self, request) -> None:
        if request is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentError(
                "Cannot deploy from a None request."
            )

        if not isinstance(
            request,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentRequest,
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentError(
                "Cannot deploy: request must be a "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupDeploymentRequest."
            )
