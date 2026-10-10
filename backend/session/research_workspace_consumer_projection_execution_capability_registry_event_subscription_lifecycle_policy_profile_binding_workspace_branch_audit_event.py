from dataclasses import (
    dataclass,
    field,
)

from datetime import datetime

from types import MappingProxyType

from typing import Mapping

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_branch_audit_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchAuditError,
)

_VALID_EVENT_TYPES = (
    "edit",
    "review",
    "merge",
    "rebase",
    "sync",
    "recovery",
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchAuditEvent:
    """
    Immutable record of a single occasion something happened to a
    consumer projection execution capability registry event
    subscription lifecycle policy profile binding workspace branch,
    kept for traceability, debugging, and compliance.

    The event is a value object only. It performs no recording and
    has no effect on the branch's operational state. It is meant to
    be recorded by whoever performs an action against a branch —
    editing its change sets, reviewing them, merging, rebasing,
    synchronizing, archiving, or restoring — rather than by the
    services that perform those actions themselves.

    Attributes:
        event_id: The event's unique identifier
        branch_id: The identifier of the branch the event concerns
        event_type: The kind of activity this event captures (one of
            "edit", "review", "merge", "rebase", "sync", or
            "recovery", where "recovery" covers both archiving and
            restoring)
        actor: The identifier of the user, service, or system that
            performed the activity
        timestamp: When the activity occurred
        metadata: Structured, activity-specific details, such as a
            change set ID, review outcome, or conflict count; empty if
            none apply
    """

    event_id: str

    branch_id: str

    event_type: str

    actor: str

    timestamp: datetime

    metadata: Mapping = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self):
        if self.event_id is None or not self.event_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchAuditError(
                "Cannot build a branch audit event with an empty or blank event ID."
            )

        if self.branch_id is None or not self.branch_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchAuditError(
                "Cannot build a branch audit event with an empty or blank branch ID."
            )

        if self.event_type is None or not self.event_type.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchAuditError(
                "Cannot build a branch audit event with an empty or blank event type."
            )

        if self.event_type not in _VALID_EVENT_TYPES:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchAuditError(
                f"Invalid branch audit event type {self.event_type!r}. Must be one of {_VALID_EVENT_TYPES!r}."
            )

        if self.actor is None or not self.actor.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchAuditError(
                "Cannot build a branch audit event with an empty or blank actor."
            )

        if self.timestamp is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchAuditError(
                "Cannot build a branch audit event with a None timestamp."
            )

        if self.metadata is None or not isinstance(self.metadata, Mapping):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchAuditError(
                "Cannot build a branch audit event with metadata that is not a mapping."
            )
