from dataclasses import (
    dataclass,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_policy_audit_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyAuditError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyDriftResult:
    """
    Immutable outcome of comparing a consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding workspace execution session's actual, effective
    configuration against its approved, published policy version's
    configuration.

    The result is a value object only. It performs no comparison.
    Producing this outcome is the responsibility of a session policy
    audit service.

    Attributes:
        session_id: The identifier of the session this result
            concerns
        compliant: Whether the session's actual configuration matches
            its approved configuration exactly
        differences: The configuration fields, if any, where the
            session's actual configuration diverges from its approved
            configuration; always empty when compliant is True
    """

    session_id: str

    compliant: bool

    differences: tuple[str, ...]

    def __post_init__(self):
        if self.session_id is None or not self.session_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyAuditError(
                "Cannot build a session policy drift result with an empty or blank session ID."
            )

        if self.compliant is None or not isinstance(self.compliant, bool):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyAuditError(
                "Cannot build a session policy drift result with a non-boolean compliant."
            )

        if self.differences is None or not isinstance(self.differences, tuple):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyAuditError(
                "Cannot build a session policy drift result with differences that is not a tuple."
            )

        for difference in self.differences:
            if difference is None or not isinstance(difference, str) or not difference.strip():
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyAuditError(
                    "Cannot build a session policy drift result with an empty, blank, or non-string difference."
                )

        if self.compliant and self.differences:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyAuditError(
                "Cannot build a compliant session policy drift result with differences."
            )

        if not self.compliant and not self.differences:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyAuditError(
                "Cannot build a non-compliant session policy drift result without differences."
            )
