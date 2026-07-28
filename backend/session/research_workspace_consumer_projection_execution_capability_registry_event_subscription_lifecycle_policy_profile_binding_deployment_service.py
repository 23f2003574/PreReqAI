from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_deployment_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_deployment_request import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentRequest,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_deployment_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_state import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingState,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentService:
    """
    Deploys validated consumer projection execution capability
    registry event subscription lifecycle policy profile bindings
    into runtime, so execution capabilities consume a consistent
    active binding set.

    The service's responsibility is orchestrating deployment, not
    binding creation, activation, or version publication themselves.
    It does NOT create bindings, activate or deactivate bindings,
    publish versions, mutate the binding registry or version
    history, persist results, log, or publish events.

    The service is:
    - Thread-safe: Active deployment bookkeeping is guarded by an
      internal lock
    - Conflict-aware: deploy() rejects a binding that already has an
      active deployment; redeploy() replaces it atomically instead
    - Active-only: Only a binding whose activation state is ACTIVE
      may be deployed or redeployed
    """

    def __init__(
        self,
        binding_registry,
        activation_service,
        binding_version_service,
        version_service,
        release_service,
    ):
        """
        Args:
            binding_registry: The registry used to resolve a binding
                ID to its profile ID. Any object exposing
                `find(binding_id)` is accepted
            activation_service: The service used to verify a binding
                is active. Any object exposing `state(binding_id)` is
                accepted
            binding_version_service: The service used to resolve a
                binding's currently selected version when none is
                given explicitly. Any object exposing
                `resolve_version(binding_id)` is accepted
            version_service: The version service used to verify an
                explicit version was published. Any object exposing
                `find(profile_id, version)` is accepted
            release_service: The release service used to verify an
                explicit version is currently released. Any object
                exposing `is_released(profile_id, version)` is
                accepted
        """

        for dependency, name in (
            (binding_registry, "binding registry"),
            (activation_service, "activation service"),
            (binding_version_service, "binding version service"),
            (version_service, "version service"),
            (release_service, "release service"),
        ):
            if dependency is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentError(
                    f"Cannot initialize deployment service with a None {name}."
                )

        self._binding_registry = binding_registry
        self._activation_service = activation_service
        self._binding_version_service = binding_version_service
        self._version_service = version_service
        self._release_service = release_service
        self._active_deployments = {}
        self._lock = RLock()

    def deploy(
        self,
        request: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentRequest,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentResult:
        """
        Deploy a binding into its target environment.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentError:
                If the request is malformed, no binding is registered
                under its binding ID, the binding is not currently
                active, its profile version cannot be resolved, or the
                binding already has an active deployment
        """

        self._validate_request(request)

        binding = self._resolve_binding(request.binding_id)

        with self._lock:
            if request.binding_id in self._active_deployments:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentError(
                    f"Cannot deploy: binding ID {request.binding_id!r} already has an active deployment."
                )

            return self._deploy_locked(
                binding,
                request.binding_id,
                request.version,
                f"deployment::{request.binding_id}",
            )

    def redeploy(
        self,
        binding_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentResult:
        """
        Atomically replace a binding's current active deployment,
        re-resolving its currently selected profile version.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentError:
                If the binding ID is None or blank, no binding is
                registered under it, no deployment is currently active
                for it, the binding is not currently active, or its
                profile version cannot be resolved
        """

        binding = self._resolve_binding(binding_id)

        with self._lock:
            existing = self._active_deployments.get(binding_id)

            if existing is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentError(
                    f"Cannot redeploy: binding ID {binding_id!r} has no active deployment."
                )

            return self._deploy_locked(
                binding,
                binding_id,
                None,
                existing.deployment_id,
            )

    def undeploy(self, binding_id: str) -> None:
        """
        Remove a binding's active deployment.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentError:
                If the binding ID is None or blank, no binding is
                registered under it, or no deployment is currently
                active for it
        """

        self._resolve_binding(binding_id)

        with self._lock:
            if binding_id not in self._active_deployments:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentError(
                    f"Cannot undeploy: binding ID {binding_id!r} has no active deployment."
                )

            del self._active_deployments[binding_id]

    def deployment(self, binding_id: str):
        """
        Look up a binding's currently active deployment.

        Returns:
            The active deployment result for binding_id, or None if
            it has no active deployment

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentError:
                If the binding ID is None or blank, or no binding is
                registered under it
        """

        self._resolve_binding(binding_id)

        with self._lock:
            return self._active_deployments.get(binding_id)

    def _deploy_locked(
        self,
        binding,
        binding_id: str,
        explicit_version,
        deployment_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentResult:
        if self._activation_service.state(binding_id) != ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingState.ACTIVE:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentError(
                f"Cannot deploy: binding ID {binding_id!r} is not currently active."
            )

        resolved_version = self._resolve_version(binding_id, binding.profile_id, explicit_version)

        if resolved_version is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentError(
                f"Cannot deploy: no released profile version could be resolved for binding ID {binding_id!r}."
            )

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentResult(
            deployment_id=deployment_id,
            binding_id=binding_id,
            deployed_version=resolved_version,
            successful=True,
        )

        self._active_deployments[binding_id] = result

        return result

    def _resolve_version(self, binding_id: str, profile_id: str, explicit_version):
        if explicit_version is not None:
            if self._version_service.find(profile_id, explicit_version) is None:
                return None

            if not self._release_service.is_released(profile_id, explicit_version):
                return None

            return explicit_version

        version_result = self._binding_version_service.resolve_version(binding_id)

        return version_result.version if version_result.resolved else None

    def _resolve_binding(self, binding_id: str):
        self._validate_identifier(binding_id, "binding ID")

        binding = self._binding_registry.find(binding_id)

        if binding is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentError(
                f"Cannot operate: no binding is registered under binding ID {binding_id!r}."
            )

        return binding

    def _validate_identifier(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentError(
                f"Cannot operate with an empty or blank {label}."
            )

    def _validate_request(self, request) -> None:
        if request is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentError(
                "Cannot deploy from a None request."
            )

        if not isinstance(
            request,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentRequest,
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentError(
                "Cannot deploy: request must be a "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingDeploymentRequest."
            )
