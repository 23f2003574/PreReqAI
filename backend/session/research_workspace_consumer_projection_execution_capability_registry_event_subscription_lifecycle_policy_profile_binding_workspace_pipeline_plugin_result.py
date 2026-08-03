from dataclasses import (
    dataclass,
    field,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_pipeline_plugin_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelinePluginError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelinePluginResult:
    """
    Immutable outcome produced after a consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding workspace pipeline plugin service attempted to run a
    plugin.

    The result is a value object only. It performs no execution.
    Execution is the responsibility of a pipeline plugin service.

    Attributes:
        plugin_id: The identifier of the plugin this result concerns
        executed: Whether the plugin's handler was invoked; False
            when the plugin was skipped because it was disabled
        duration_ms: How long the handler took to run, in
            milliseconds; 0.0 when the plugin was skipped
        error: The plugin's failure message, if its handler raised;
            None if it succeeded or was skipped
    """

    plugin_id: str

    executed: bool

    duration_ms: float

    error: str = field(default=None)

    def __post_init__(self):
        if self.plugin_id is None or not self.plugin_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelinePluginError(
                "Cannot build a pipeline plugin result with an empty or blank plugin ID."
            )

        if not isinstance(self.executed, bool):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelinePluginError(
                "Cannot build a pipeline plugin result with a non-boolean executed flag."
            )

        if (
            self.duration_ms is None
            or isinstance(self.duration_ms, bool)
            or not isinstance(self.duration_ms, (int, float))
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelinePluginError(
                "Cannot build a pipeline plugin result with a non-numeric duration_ms."
            )

        if self.duration_ms < 0:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelinePluginError(
                "Cannot build a pipeline plugin result with a negative duration_ms."
            )

        if self.error is not None and not isinstance(self.error, str):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelinePluginError(
                "Cannot build a pipeline plugin result with a non-string error."
            )
