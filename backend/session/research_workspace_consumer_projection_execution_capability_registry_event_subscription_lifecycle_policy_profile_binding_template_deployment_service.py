from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBinding,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_template_deployment_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_template_deployment_request import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentRequest,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_template_deployment_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentResult,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentService:
    """
    Atomically deploys a published, currently released version of a
    consumer projection execution capability registry event
    subscription lifecycle policy profile binding template into a
    target runtime environment, by instantiating independent copies
    of every binding the version snapshot references and activating
    each of them, as a single operation.

    The service's responsibility is orchestrating deployment, not
    template registration, version publication, or parameter
    handling themselves. It does NOT register templates, mutate a
    template's membership, publish or roll back versions, persist
    results, log, or publish events.

    The service is:
    - Thread-safe: Active deployment bookkeeping and binding
      instantiation are guarded by an internal lock
    - Conflict-aware: deploy() rejects a template that already has an
      active deployment; redeploy() replaces it atomically instead
    - Atomic: Every source binding is validated before any binding is
      instantiated, registered, or activated, so a single unknown
      source binding fails the whole deployment, leaving no partial
      deployment in place
    - Released-only: Only the template's currently released (its
      version history's current) version may be deployed
    - Copy-independent: Every deployment instantiates brand-new
      binding records; no instantiated binding is shared between
      deployments or with the source bindings the version was built
      from
    """

    def __init__(
        self,
        template_version_service,
        binding_registry,
        activation_service,
    ):
        """
        Args:
            template_version_service: The service used to resolve a
                published template version and verify it is currently
                released. Any object exposing `find(template_id,
                version)` and `latest(template_id)` is accepted
            binding_registry: The registry used to resolve a version
                snapshot's source bindings, and to register the
                bindings instantiated for a deployment. Any object
                exposing `find(binding_id)` and `register(binding)` is
                accepted
            activation_service: The service used to activate every
                instantiated binding. Any object exposing
                `activate(binding_id)` is accepted
        """

        for dependency, name in (
            (template_version_service, "template version service"),
            (binding_registry, "binding registry"),
            (activation_service, "activation service"),
        ):
            if dependency is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentError(
                    f"Cannot initialize deployment service with a None {name}."
                )

        self._template_version_service = template_version_service
        self._binding_registry = binding_registry
        self._activation_service = activation_service
        self._active_deployments = {}
        self._sequence = 0
        self._lock = RLock()

    def deploy(
        self,
        request: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentRequest,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentResult:
        """
        Deploy a template's published version into its target
        environment.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentError:
                If the request is malformed, no such template version
                has been published, the version is not currently
                released, any source binding referenced by the
                version is unknown, or the template already has an
                active deployment
        """

        self._validate_request(request)

        with self._lock:
            if request.template_id in self._active_deployments:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentError(
                    f"Cannot deploy: template ID {request.template_id!r} already has an active deployment."
                )

            return self._deploy_locked(
                request.template_id,
                request.version,
                f"deployment::{request.template_id}",
            )

    def redeploy(
        self,
        template_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentResult:
        """
        Atomically replace a template's current active deployment,
        re-resolving its currently released version and instantiating
        a fresh set of bindings for it.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentError:
                If the template ID is None or blank, no deployment is
                currently active for it, or its currently released
                version can no longer be deployed
        """

        self._validate_identifier(template_id, "template ID")

        with self._lock:
            existing = self._active_deployments.get(template_id)

            if existing is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentError(
                    f"Cannot redeploy: template ID {template_id!r} has no active deployment."
                )

            current = self._template_version_service.latest(template_id)

            return self._deploy_locked(template_id, current.version, existing.deployment_id)

    def undeploy(self, template_id: str) -> None:
        """
        Remove a template's active deployment.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentError:
                If the template ID is None or blank, or no deployment
                is currently active for it
        """

        self._validate_identifier(template_id, "template ID")

        with self._lock:
            if template_id not in self._active_deployments:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentError(
                    f"Cannot undeploy: template ID {template_id!r} has no active deployment."
                )

            del self._active_deployments[template_id]

    def deployment(self, template_id: str):
        """
        Look up a template's currently active deployment.

        Returns:
            The active deployment result for template_id, or None if
            it has no active deployment

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentError:
                If the template ID is None or blank
        """

        self._validate_identifier(template_id, "template ID")

        with self._lock:
            return self._active_deployments.get(template_id)

    def _deploy_locked(
        self,
        template_id: str,
        version: str,
        deployment_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentResult:
        snapshot = self._resolve_released_version(template_id, version)

        sources = []

        for binding_id in snapshot.binding_ids:
            source = self._binding_registry.find(binding_id)

            if source is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentError(
                    f"Cannot deploy: no binding is registered under binding ID {binding_id!r}."
                )

            sources.append(source)

        instantiated = []

        for source in sources:
            self._sequence += 1

            instance = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBinding(
                binding_id=f"{deployment_id}::{source.binding_id}::{self._sequence}",
                profile_id=source.profile_id,
                capability_id=source.capability_id,
                created_at=datetime.now(timezone.utc),
            )

            self._binding_registry.register(instance)
            self._activation_service.activate(instance.binding_id)

            instantiated.append(instance)

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentResult(
            deployment_id=deployment_id,
            instantiated_bindings=tuple(instantiated),
            successful=True,
        )

        self._active_deployments[template_id] = result

        return result

    def _resolve_released_version(self, template_id: str, version: str):
        snapshot = self._template_version_service.find(template_id, version)

        if snapshot is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentError(
                f"Cannot deploy: no version {version!r} has been published for template ID {template_id!r}."
            )

        current = self._template_version_service.latest(template_id)

        if current.version != version:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentError(
                f"Cannot deploy: version {version!r} is not the currently released version for template ID {template_id!r}."
            )

        return snapshot

    def _validate_identifier(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentError(
                f"Cannot operate with an empty or blank {label}."
            )

    def _validate_request(self, request) -> None:
        if request is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentError(
                "Cannot deploy from a None request."
            )

        if not isinstance(
            request,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentRequest,
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentError(
                "Cannot deploy: request must be a "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateDeploymentRequest."
            )
