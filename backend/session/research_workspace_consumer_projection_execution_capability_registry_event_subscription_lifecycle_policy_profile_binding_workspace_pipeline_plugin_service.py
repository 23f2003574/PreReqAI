from dataclasses import (
    replace,
)

from threading import (
    RLock,
)

from time import perf_counter

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_pipeline_plugin_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelinePluginError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_pipeline_plugin import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelinePlugin,
    VALID_PLUGIN_STAGE_TYPES,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_pipeline_plugin_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelinePluginResult,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelinePluginService:
    """
    Runs extensible plugins at defined consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding workspace execution pipeline stage types, without the
    pipeline's core execution engine knowing anything about a
    specific plugin's logic.

    The service's responsibility is registration, enablement, and
    dispatch, not running a pipeline itself. It does NOT execute
    stages or pipelines; whoever runs a stage (for example, a stage
    executor bound into a consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    workspace execution pipeline service) is expected to call
    execute() as part of running its stage type.

    Behavior:
    - Plugins for a stage type run in the order they were registered
    - A disabled plugin is skipped, not run
    - A plugin whose handler raises does not prevent execution of the
      other plugins for that stage, and does not propagate past
      execute(); the failure is captured in its result instead

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock; plugin handlers run outside the lock, so a handler that
      calls back into the service cannot deadlock it
    """

    def __init__(self):
        self._plugins = {}
        self._handlers = {}
        self._registration_order = []
        self._lock = RLock()

    def register(self, plugin: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelinePlugin, handler) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelinePlugin:
        """
        Register a plugin and the handler it runs.

        Args:
            plugin: The plugin's descriptor
            handler: A callable accepting (stage_id) that performs
                the plugin's work

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelinePluginError:
                If plugin is None or not a ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelinePlugin, handler is not
                callable, or the plugin's ID is already registered
        """

        if plugin is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelinePluginError(
                "Cannot register a None pipeline plugin."
            )

        if not isinstance(plugin, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelinePlugin):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelinePluginError(
                "Cannot register a pipeline plugin: plugin must be a "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelinePlugin."
            )

        if not callable(handler):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelinePluginError(
                "Cannot register a pipeline plugin with a handler that is not callable."
            )

        with self._lock:
            if plugin.plugin_id in self._plugins:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelinePluginError(
                    f"Plugin ID {plugin.plugin_id!r} is already registered."
                )

            self._plugins[plugin.plugin_id] = plugin
            self._handlers[plugin.plugin_id] = handler
            self._registration_order.append(plugin.plugin_id)

            return plugin

    def enable(self, plugin_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelinePlugin:
        """
        Enable a registered plugin.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelinePluginError:
                If plugin_id is None or blank, or no plugin is
                registered under it
        """

        return self._set_enabled(plugin_id, True)

    def disable(self, plugin_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelinePlugin:
        """
        Disable a registered plugin.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelinePluginError:
                If plugin_id is None or blank, or no plugin is
                registered under it
        """

        return self._set_enabled(plugin_id, False)

    def execute(self, stage_id: str, stage_type: str) -> tuple:
        """
        Run every enabled plugin registered for a stage type, in
        registration order.

        Args:
            stage_id: The identifier of the stage instance being run;
                passed through to each plugin's handler
            stage_type: The stage type whose plugins should run

        Returns:
            One result per plugin registered for stage_type, in
            registration order

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelinePluginError:
                If stage_id or stage_type is None or blank, or
                stage_type is not a recognized stage type
        """

        self._validate_id(stage_id, "stage ID")
        self._validate_stage_type(stage_type)

        with self._lock:
            matching_ids = [
                plugin_id
                for plugin_id in self._registration_order
                if self._plugins[plugin_id].stage_type == stage_type
            ]

        results = []

        for plugin_id in matching_ids:
            with self._lock:
                plugin = self._plugins[plugin_id]
                handler = self._handlers[plugin_id]

            if not plugin.enabled:
                results.append(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelinePluginResult(plugin_id=plugin_id, executed=False, duration_ms=0.0))
                continue

            started_at = perf_counter()
            error_message = None

            try:
                handler(stage_id)
            except Exception as error:
                error_message = str(error)

            duration_ms = (perf_counter() - started_at) * 1000

            results.append(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelinePluginResult(
                    plugin_id=plugin_id,
                    executed=True,
                    duration_ms=duration_ms,
                    error=error_message,
                )
            )

        return tuple(results)

    def plugins(self, stage_type: str) -> tuple:
        """
        List every plugin registered for a stage type, in
        registration order.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelinePluginError:
                If stage_type is None or blank, or not a recognized
                stage type
        """

        self._validate_stage_type(stage_type)

        with self._lock:
            return tuple(
                self._plugins[plugin_id]
                for plugin_id in self._registration_order
                if self._plugins[plugin_id].stage_type == stage_type
            )

    def _set_enabled(self, plugin_id: str, enabled: bool) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelinePlugin:
        self._validate_id(plugin_id, "plugin ID")

        with self._lock:
            plugin = self._plugins.get(plugin_id)

            if plugin is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelinePluginError(
                    f"No pipeline plugin is registered under plugin ID {plugin_id!r}."
                )

            updated = replace(plugin, enabled=enabled)
            self._plugins[plugin_id] = updated

            return updated

    def _validate_stage_type(self, stage_type: str) -> None:
        if stage_type is None or not stage_type.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelinePluginError(
                "Cannot operate with an empty or blank stage type."
            )

        if stage_type not in VALID_PLUGIN_STAGE_TYPES:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelinePluginError(
                f"Invalid pipeline plugin stage type {stage_type!r}. Must be one of "
                f"{VALID_PLUGIN_STAGE_TYPES!r}."
            )

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelinePluginError(
                f"Cannot operate with an empty or blank {label}."
            )
