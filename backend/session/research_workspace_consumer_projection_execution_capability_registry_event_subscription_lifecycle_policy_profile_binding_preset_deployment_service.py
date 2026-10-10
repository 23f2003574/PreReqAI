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

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_preset_deployment_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_preset_deployment_request import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentRequest,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_preset_deployment_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentResult,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentService:
    """
    Atomically deploys a published, currently released version of a
    consumer projection execution capability registry event
    subscription lifecycle policy profile binding preset into a
    target runtime environment, by instantiating independent copies
    of every binding referenced by the version snapshot's member
    binding templates and activating each of them, as a single
    operation.

    The service's responsibility is orchestrating deployment, not
    preset registration, version publication, or parameter handling
    themselves. It does NOT register presets, mutate a preset's
    membership, publish or roll back versions, persist results, log,
    or publish events.

    The service is:
    - Thread-safe: Active deployment bookkeeping and binding
      instantiation are guarded by an internal lock
    - Conflict-aware: deploy() rejects a preset that already has an
      active deployment; redeploy() replaces it atomically instead
    - Atomic: Every referenced binding template, and every source
      binding it is built from, is validated before any binding is
      instantiated, registered, or activated, so a single unknown
      template or source binding fails the whole deployment, leaving
      no partial deployment in place
    - Released-only: Only the preset's currently released (its
      version history's current) version may be deployed
    - Copy-independent: Every deployment instantiates brand-new
      binding records; no instantiated binding is shared between
      deployments or with the source bindings the version was built
      from
    """

    def __init__(
        self,
        preset_version_service,
        template_registry,
        binding_registry,
        activation_service,
    ):
        """
        Args:
            preset_version_service: The service used to resolve a
                published preset version and verify it is currently
                released. Any object exposing `find(preset_id,
                version)` and `latest(preset_id)` is accepted
            template_registry: The registry used to resolve a version
                snapshot's member binding templates. Any object
                exposing `find(template_id)`, returning an object with
                a `binding_ids` collection, is accepted
            binding_registry: The registry used to resolve a binding
                template's source bindings, and to register the
                bindings instantiated for a deployment. Any object
                exposing `find(binding_id)` and `register(binding)` is
                accepted
            activation_service: The service used to activate every
                instantiated binding. Any object exposing
                `activate(binding_id)` is accepted
        """

        for dependency, name in (
            (preset_version_service, "preset version service"),
            (template_registry, "template registry"),
            (binding_registry, "binding registry"),
            (activation_service, "activation service"),
        ):
            if dependency is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentError(
                    f"Cannot initialize deployment service with a None {name}."
                )

        self._preset_version_service = preset_version_service
        self._template_registry = template_registry
        self._binding_registry = binding_registry
        self._activation_service = activation_service
        self._active_deployments = {}
        self._sequence = 0
        self._lock = RLock()

    def deploy(
        self,
        request: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentRequest,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentResult:
        """
        Deploy a preset's published version into its target
        environment.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentError:
                If the request is malformed, no such preset version
                has been published, the version is not currently
                released, any referenced binding template or source
                binding is unknown, or the preset already has an
                active deployment
        """

        self._validate_request(request)

        with self._lock:
            if request.preset_id in self._active_deployments:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentError(
                    f"Cannot deploy: preset ID {request.preset_id!r} already has an active deployment."
                )

            return self._deploy_locked(
                request.preset_id,
                request.version,
                f"deployment::{request.preset_id}",
            )

    def redeploy(
        self,
        preset_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentResult:
        """
        Atomically replace a preset's current active deployment,
        re-resolving its currently released version and instantiating
        a fresh set of bindings for it.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentError:
                If the preset ID is None or blank, no deployment is
                currently active for it, or its currently released
                version can no longer be deployed
        """

        self._validate_identifier(preset_id, "preset ID")

        with self._lock:
            existing = self._active_deployments.get(preset_id)

            if existing is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentError(
                    f"Cannot redeploy: preset ID {preset_id!r} has no active deployment."
                )

            current = self._preset_version_service.latest(preset_id)

            return self._deploy_locked(preset_id, current.version, existing.deployment_id)

    def undeploy(self, preset_id: str) -> None:
        """
        Remove a preset's active deployment.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentError:
                If the preset ID is None or blank, or no deployment
                is currently active for it
        """

        self._validate_identifier(preset_id, "preset ID")

        with self._lock:
            if preset_id not in self._active_deployments:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentError(
                    f"Cannot undeploy: preset ID {preset_id!r} has no active deployment."
                )

            del self._active_deployments[preset_id]

    def deployment(self, preset_id: str):
        """
        Look up a preset's currently active deployment.

        Returns:
            The active deployment result for preset_id, or None if it
            has no active deployment

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentError:
                If the preset ID is None or blank
        """

        self._validate_identifier(preset_id, "preset ID")

        with self._lock:
            return self._active_deployments.get(preset_id)

    def _deploy_locked(
        self,
        preset_id: str,
        version: str,
        deployment_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentResult:
        snapshot = self._resolve_released_version(preset_id, version)

        sources_by_template = []

        for template_id in snapshot.template_ids:
            template = self._template_registry.find(template_id)

            if template is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentError(
                    f"Cannot deploy: no binding template is registered under template ID {template_id!r}."
                )

            sources = []

            for binding_id in template.binding_ids:
                source = self._binding_registry.find(binding_id)

                if source is None:
                    raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentError(
                        f"Cannot deploy: no binding is registered under binding ID {binding_id!r}."
                    )

                sources.append(source)

            sources_by_template.append((template_id, sources))

        instantiated_ids = []

        for template_id, sources in sources_by_template:
            for source in sources:
                self._sequence += 1

                instance = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBinding(
                    binding_id=f"{deployment_id}::{template_id}::{source.binding_id}::{self._sequence}",
                    profile_id=source.profile_id,
                    capability_id=source.capability_id,
                    created_at=datetime.now(timezone.utc),
                )

                self._binding_registry.register(instance)
                self._activation_service.activate(instance.binding_id)

                instantiated_ids.append(instance.binding_id)

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentResult(
            deployment_id=deployment_id,
            instantiated_binding_ids=tuple(instantiated_ids),
            successful=True,
        )

        self._active_deployments[preset_id] = result

        return result

    def _resolve_released_version(self, preset_id: str, version: str):
        snapshot = self._preset_version_service.find(preset_id, version)

        if snapshot is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentError(
                f"Cannot deploy: no version {version!r} has been published for preset ID {preset_id!r}."
            )

        current = self._preset_version_service.latest(preset_id)

        if current.version != version:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentError(
                f"Cannot deploy: version {version!r} is not the currently released version for preset ID {preset_id!r}."
            )

        return snapshot

    def _validate_identifier(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentError(
                f"Cannot operate with an empty or blank {label}."
            )

    def _validate_request(self, request) -> None:
        if request is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentError(
                "Cannot deploy from a None request."
            )

        if not isinstance(
            request,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentRequest,
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentError(
                "Cannot deploy: request must be a "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetDeploymentRequest."
            )
