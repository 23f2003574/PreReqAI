from dataclasses import (
    dataclass,
    field,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_pipeline_plugin_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelinePluginError,
)

VALID_PLUGIN_STAGE_TYPES = (
    "validation",
    "review",
    "merge",
    "deployment",
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelinePlugin:
    """
    Immutable descriptor of an extension a consumer projection
    execution capability registry event subscription lifecycle
    policy profile binding workspace execution pipeline runs at a
    given stage type, without the pipeline's core execution engine
    knowing anything about it.

    The plugin is a value object only. It performs no execution.
    Execution is the responsibility of a pipeline plugin service,
    dispatching to the handler the plugin was registered with.

    Attributes:
        plugin_id: The plugin's unique identifier
        name: The plugin's human-readable name
        stage_type: The stage type the plugin runs at, one of
            "validation", "review", "merge", or "deployment"
        enabled: Whether the plugin currently runs when its stage
            type executes
    """

    plugin_id: str

    name: str

    stage_type: str

    enabled: bool = field(default=True)

    def __post_init__(self):
        if self.plugin_id is None or not self.plugin_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelinePluginError(
                "Cannot build a pipeline plugin with an empty or blank plugin ID."
            )

        if self.name is None or not self.name.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelinePluginError(
                "Cannot build a pipeline plugin with an empty or blank name."
            )

        if self.stage_type is None or not self.stage_type.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelinePluginError(
                "Cannot build a pipeline plugin with an empty or blank stage type."
            )

        if self.stage_type not in VALID_PLUGIN_STAGE_TYPES:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelinePluginError(
                f"Invalid pipeline plugin stage type {self.stage_type!r}. Must be one of "
                f"{VALID_PLUGIN_STAGE_TYPES!r}."
            )

        if not isinstance(self.enabled, bool):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelinePluginError(
                "Cannot build a pipeline plugin with a non-boolean enabled flag."
            )
