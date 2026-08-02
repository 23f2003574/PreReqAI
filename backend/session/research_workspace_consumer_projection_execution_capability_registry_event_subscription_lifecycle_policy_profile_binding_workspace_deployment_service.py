from threading import (
    RLock,
)

from types import MappingProxyType

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_deployment_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_deployment_request import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentRequest,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_deployment_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentResult,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentService:
    """
    Atomically deploys a published, currently released version of a
    consumer projection execution capability registry event
    subscription lifecycle policy profile binding workspace into a
    target runtime environment, as a single, consistent runtime
    configuration built from every binding, binding template, binding
    preset, and binding group the workspace currently references.

    The service's responsibility is orchestrating deployment, not
    workspace registration, membership management, or version
    publication themselves. It does NOT register workspaces, mutate a
    workspace's membership, publish or roll back versions, persist
    results, log, or publish events.

    The service is:
    - Thread-safe: Active deployment bookkeeping is guarded by an
      internal lock
    - Conflict-aware: deploy() rejects a workspace that already has
      an active deployment; redeploy() replaces it atomically instead
    - Atomic: Every referenced binding, binding template, binding
      preset, and binding group is validated as registered before any
      deployment record is committed, so a single unknown reference
      fails the whole deployment, leaving no partial deployment in
      place
    - Released-only: Only the workspace's currently released (its
      version history's current) version may be deployed
    """

    def __init__(
        self,
        workspace_version_service,
        workspace_registry,
        binding_registry,
        template_registry,
        preset_registry,
        group_registry,
    ):
        """
        Args:
            workspace_version_service: The service used to resolve a
                published workspace version and verify it is
                currently released. Any object exposing
                `find(workspace_id, version)` and `latest(workspace_id)`
                is accepted
            workspace_registry: The registry used to resolve a
                workspace's current referenced resources. Any object
                exposing `find(workspace_id)` is accepted
            binding_registry: The registry used to verify that a
                referenced binding is registered. Any object exposing
                `find(binding_id)` is accepted
            template_registry: The registry used to verify that a
                referenced binding template is registered. Any object
                exposing `find(template_id)` is accepted
            preset_registry: The registry used to verify that a
                referenced binding preset is registered. Any object
                exposing `find(preset_id)` is accepted
            group_registry: The registry used to verify that a
                referenced binding group is registered. Any object
                exposing `find(group_id)` is accepted

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentError:
                If any dependency is None
        """

        for dependency, name in (
            (workspace_version_service, "workspace version service"),
            (workspace_registry, "workspace registry"),
            (binding_registry, "binding registry"),
            (template_registry, "binding template registry"),
            (preset_registry, "binding preset registry"),
            (group_registry, "binding group registry"),
        ):
            if dependency is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentError(
                    f"Cannot initialize deployment service with a None {name}."
                )

        self._workspace_version_service = workspace_version_service
        self._workspace_registry = workspace_registry
        self._binding_registry = binding_registry
        self._template_registry = template_registry
        self._preset_registry = preset_registry
        self._group_registry = group_registry
        self._active_deployments = {}
        self._lock = RLock()

    def deploy(
        self,
        request: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentRequest,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentResult:
        """
        Deploy a workspace's published version into its target
        environment.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentError:
                If the request is malformed, no such workspace version
                has been published, the version is not currently
                released, any referenced resource is unknown, or the
                workspace already has an active deployment
        """

        self._validate_request(request)

        with self._lock:
            if request.workspace_id in self._active_deployments:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentError(
                    f"Cannot deploy: workspace ID {request.workspace_id!r} already has an active deployment."
                )

            return self._deploy_locked(
                request.workspace_id,
                request.version,
                f"deployment::{request.workspace_id}",
            )

    def redeploy(
        self,
        workspace_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentResult:
        """
        Atomically replace a workspace's current active deployment,
        re-resolving its currently released version and its current
        referenced resources.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentError:
                If the workspace ID is None or blank, no deployment is
                currently active for it, or its currently released
                version can no longer be deployed
        """

        self._validate_identifier(workspace_id, "workspace ID")

        with self._lock:
            existing = self._active_deployments.get(workspace_id)

            if existing is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentError(
                    f"Cannot redeploy: workspace ID {workspace_id!r} has no active deployment."
                )

            current = self._workspace_version_service.latest(workspace_id)

            return self._deploy_locked(workspace_id, current.version, existing.deployment_id)

    def undeploy(self, workspace_id: str) -> None:
        """
        Remove a workspace's active deployment.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentError:
                If the workspace ID is None or blank, or no deployment
                is currently active for it
        """

        self._validate_identifier(workspace_id, "workspace ID")

        with self._lock:
            if workspace_id not in self._active_deployments:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentError(
                    f"Cannot undeploy: workspace ID {workspace_id!r} has no active deployment."
                )

            del self._active_deployments[workspace_id]

    def deployment(self, workspace_id: str):
        """
        Look up a workspace's currently active deployment.

        Returns:
            The active deployment result for workspace_id, or None if
            it has no active deployment

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentError:
                If the workspace ID is None or blank
        """

        self._validate_identifier(workspace_id, "workspace ID")

        with self._lock:
            return self._active_deployments.get(workspace_id)

    def _deploy_locked(
        self,
        workspace_id: str,
        version: str,
        deployment_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentResult:
        self._resolve_released_version(workspace_id, version)

        workspace = self._workspace_registry.find(workspace_id)

        if workspace is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentError(
                f"Cannot deploy: no workspace is registered under workspace ID {workspace_id!r}."
            )

        deployed_resources = {}

        for kind, label, member_ids, registry in (
            ("bindings", "binding", workspace.binding_ids, self._binding_registry),
            ("templates", "binding template", workspace.template_ids, self._template_registry),
            ("presets", "binding preset", workspace.preset_ids, self._preset_registry),
            ("groups", "binding group", workspace.group_ids, self._group_registry),
        ):
            resolved_ids = []

            for member_id in member_ids:
                if registry.find(member_id) is None:
                    raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentError(
                        f"Cannot deploy: no {label} is registered under ID {member_id!r}."
                    )

                resolved_ids.append(member_id)

            deployed_resources[kind] = tuple(resolved_ids)

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentResult(
            deployment_id=deployment_id,
            deployed_resources=MappingProxyType(deployed_resources),
            successful=True,
        )

        self._active_deployments[workspace_id] = result

        return result

    def _resolve_released_version(self, workspace_id: str, version: str) -> None:
        published = self._workspace_version_service.find(workspace_id, version)

        if published is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentError(
                f"Cannot deploy: no version {version!r} has been published for workspace ID {workspace_id!r}."
            )

        current = self._workspace_version_service.latest(workspace_id)

        if current.version != version:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentError(
                f"Cannot deploy: version {version!r} is not the currently released version for workspace ID {workspace_id!r}."
            )

    def _validate_identifier(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentError(
                f"Cannot operate with an empty or blank {label}."
            )

    def _validate_request(self, request) -> None:
        if request is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentError(
                "Cannot deploy from a None request."
            )

        if not isinstance(
            request,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentRequest,
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentError(
                "Cannot deploy: request must be a "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceDeploymentRequest."
            )
