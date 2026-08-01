from dataclasses import (
    dataclass,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_preset_audit_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetAuditError,
)

_VALID_OPERATIONS = (
    "register",
    "replace",
    "remove",
    "instantiate",
    "publish",
    "deploy",
    "redeploy",
    "undeploy",
    "rollback",
    "release",
    "retire",
    "sync",
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetAuditRecord:
    """
    Immutable record of a single consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding preset lifecycle operation, kept for traceability,
    debugging, and compliance.

    The record is a value object only. It performs no recording and
    has no effect on the preset's operational state.

    Attributes:
        audit_id: The record's unique identifier
        preset_id: The identifier of the preset the operation
            concerned
        operation: The kind of lifecycle operation this record
            captures (one of "register", "replace", "remove",
            "instantiate", "publish", "deploy", "redeploy",
            "undeploy", "rollback", "release", "retire", or "sync")
        version: The preset version the operation concerned, or None
            if the operation was not version-specific
        timestamp: When the operation occurred
        actor: The identifier of the user, service, or system that
            performed the operation
    """

    audit_id: str

    preset_id: str

    operation: str

    version: (
        str | None
    )

    timestamp: datetime

    actor: str

    def __post_init__(self):
        if self.audit_id is None or not self.audit_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetAuditError(
                "Cannot build an audit record with an empty or blank audit ID."
            )

        if self.preset_id is None or not self.preset_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetAuditError(
                "Cannot build an audit record with an empty or blank preset ID."
            )

        if self.operation is None or not self.operation.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetAuditError(
                "Cannot build an audit record with an empty or blank operation."
            )

        if self.operation not in _VALID_OPERATIONS:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetAuditError(
                f"Invalid audit record operation {self.operation!r}. Must be one of {_VALID_OPERATIONS!r}."
            )

        if self.version is not None and not self.version.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetAuditError(
                "Cannot build an audit record with a blank version; omit it entirely instead."
            )

        if self.timestamp is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetAuditError(
                "Cannot build an audit record with a None timestamp."
            )

        if self.actor is None or not self.actor.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetAuditError(
                "Cannot build an audit record with an empty or blank actor."
            )
