from dataclasses import (
    dataclass,
    field,
)

from types import MappingProxyType

from typing import Mapping

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_pipeline_execution_policy_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionPolicyError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_pipeline_timeout_policy import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineTimeoutPolicy,
)

_QUOTA_POLICY_KEYS = (
    "max_runtime",
    "max_memory",
    "max_parallel_tasks",
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionPolicy:
    """
    Immutable, reusable execution policy that controls how a
    consumer projection execution capability registry event
    subscription lifecycle policy profile binding workspace execution
    pipeline runs, without changing the pipeline's own definition.

    The policy is a value object only. It performs no assignment and
    no enforcement. Assignment and enforcement are the responsibility
    of a pipeline execution policy service, and, for the dimensions
    it configures, of the existing retry, timeout, and quota
    services.

    Attributes:
        policy_id: The policy's unique identifier
        name: The policy's human-readable, unique name
        retry_policy: Retry configuration, for example
            {"max_attempts": 3, "backoff_seconds": 5}; empty if
            retries are not configured
        timeout_policy: The
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineTimeoutPolicy
            to enforce, or None if timeout is not configured
        quota_policy: Resource quota configuration, using the same
            "max_runtime", "max_memory", and "max_parallel_tasks"
            keys a resource budget uses; empty if quotas are not
            configured
        enabled: Whether the policy is currently applied when
            assigned
    """

    policy_id: str

    name: str

    retry_policy: Mapping = field(default_factory=lambda: MappingProxyType({}))

    timeout_policy: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineTimeoutPolicy = field(default=None)

    quota_policy: Mapping = field(default_factory=lambda: MappingProxyType({}))

    enabled: bool = field(default=True)

    def __post_init__(self):
        if self.policy_id is None or not self.policy_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionPolicyError(
                "Cannot build a pipeline execution policy with an empty or blank policy ID."
            )

        if self.name is None or not self.name.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionPolicyError(
                "Cannot build a pipeline execution policy with an empty or blank name."
            )

        if self.retry_policy is None or not isinstance(self.retry_policy, Mapping):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionPolicyError(
                "Cannot build a pipeline execution policy with a retry_policy that is not a mapping."
            )

        if self.timeout_policy is not None and not isinstance(self.timeout_policy, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineTimeoutPolicy):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionPolicyError(
                "Cannot build a pipeline execution policy: timeout_policy must be a "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineTimeoutPolicy or None."
            )

        if self.quota_policy is None or not isinstance(self.quota_policy, Mapping):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionPolicyError(
                "Cannot build a pipeline execution policy with a quota_policy that is not a mapping."
            )

        for key, value in self.quota_policy.items():
            if key not in _QUOTA_POLICY_KEYS:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionPolicyError(
                    f"Invalid pipeline execution policy quota_policy key {key!r}. Must be one of "
                    f"{_QUOTA_POLICY_KEYS!r}."
                )

            if value is None or isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionPolicyError(
                    f"Cannot build a pipeline execution policy with a non-numeric quota_policy value for "
                    f"{key!r}."
                )

            if value < 0:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionPolicyError(
                    f"Cannot build a pipeline execution policy with a negative quota_policy value for "
                    f"{key!r}."
                )

        if not isinstance(self.enabled, bool):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineExecutionPolicyError(
                "Cannot build a pipeline execution policy with a non-boolean enabled flag."
            )
