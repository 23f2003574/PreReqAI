from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_compliance_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionComplianceError,
)

VALID_SESSION_COMPLIANCE_SEVERITIES = (
    "CRITICAL",
    "WARNING",
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionComplianceRule:
    """
    Immutable, reusable definition of a compliance requirement
    checked against a consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    workspace execution session before and during execution.

    The rule is a value object only. It performs no evaluation.
    Evaluating, enabling, disabling, and reporting on rules are the
    responsibility of a session compliance service.

    Attributes:
        rule_id: The rule's unique identifier
        name: A human-readable label for the rule
        severity: How serious a violation of this rule is, one of
            "CRITICAL" or "WARNING". A "CRITICAL" violation blocks
            session execution; a "WARNING" violation does not
        enabled: Whether this rule is currently evaluated
    """

    rule_id: str

    name: str

    severity: str

    enabled: bool

    def __post_init__(self):
        if self.rule_id is None or not self.rule_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionComplianceError(
                "Cannot build a session compliance rule with an empty or blank rule ID."
            )

        if self.name is None or not self.name.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionComplianceError(
                "Cannot build a session compliance rule with an empty or blank name."
            )

        if self.severity is None or not isinstance(self.severity, str) or not self.severity.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionComplianceError(
                "Cannot build a session compliance rule with an empty, blank, or non-string severity."
            )

        if self.severity not in VALID_SESSION_COMPLIANCE_SEVERITIES:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionComplianceError(
                f"Invalid session compliance rule severity {self.severity!r}. Must be one of "
                f"{VALID_SESSION_COMPLIANCE_SEVERITIES!r}."
            )

        if self.enabled is None or not isinstance(self.enabled, bool):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionComplianceError(
                "Cannot build a session compliance rule with a non-boolean enabled."
            )
