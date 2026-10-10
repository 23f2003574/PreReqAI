from dataclasses import (
    dataclass,
)

from datetime import datetime

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_template_audit_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateAuditError,
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
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateAuditRecord:
    """
    Immutable record of a single consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding template lifecycle operation, kept for traceability,
    debugging, and compliance.

    The record is a value object only. It performs no recording and
    has no effect on the template's operational state.

    Attributes:
        audit_id: The record's unique identifier
        template_id: The identifier of the template the operation
            concerned
        operation: The kind of lifecycle operation this record
            captures (one of "register", "replace", "remove",
            "instantiate", "publish", "deploy", "redeploy",
            "undeploy", "rollback", "release", "retire", or "sync")
        version: The template version the operation concerned, or
            None if the operation was not version-specific
        timestamp: When the operation occurred
        actor: The identifier of the user, service, or system that
            performed the operation
    """

    audit_id: str

    template_id: str

    operation: str

    version: (
        str | None
    )

    timestamp: datetime

    actor: str

    def __post_init__(self):
        if self.audit_id is None or not self.audit_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateAuditError(
                "Cannot build an audit record with an empty or blank audit ID."
            )

        if self.template_id is None or not self.template_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateAuditError(
                "Cannot build an audit record with an empty or blank template ID."
            )

        if self.operation is None or not self.operation.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateAuditError(
                "Cannot build an audit record with an empty or blank operation."
            )

        if self.operation not in _VALID_OPERATIONS:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateAuditError(
                f"Invalid audit record operation {self.operation!r}. Must be one of {_VALID_OPERATIONS!r}."
            )

        if self.version is not None and not self.version.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateAuditError(
                "Cannot build an audit record with a blank version; omit it entirely instead."
            )

        if self.timestamp is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateAuditError(
                "Cannot build an audit record with a None timestamp."
            )

        if self.actor is None or not self.actor.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateAuditError(
                "Cannot build an audit record with an empty or blank actor."
            )
