from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_branch_audit_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchAuditError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_branch_audit_event import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchAuditEvent,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_branch_timeline import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchTimeline,
)

_VALID_EVENT_TYPES = (
    "edit",
    "review",
    "merge",
    "rebase",
    "sync",
    "recovery",
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchAuditService:
    """
    Records every consumer projection execution capability registry
    event subscription lifecycle policy profile binding workspace
    branch activity — edits, reviews, merges, rebases,
    synchronizations, and recoveries — into an append-only, per-branch
    timeline for traceability, debugging, and compliance.

    The service's responsibility is recording and retrieving audit
    events, not performing the activities they describe. It does NOT
    stage or review change sets, merge, rebase, synchronize, protect,
    archive, or restore a branch. It operates entirely independently
    of every other branch service: it integrates with the change set,
    review, merge, rebase, synchronization, archive, and recovery
    workflows by being the log whoever performs those actions records
    into, not by depending on or being depended on by any of them.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    - Append-only: Events are never mutated or replaced once recorded,
      only added or purged
    - Duplicate-free: No two recorded events may share an event ID
    - Chronological: timeline(), latest(), events(), and list() always
      order events by timestamp, regardless of recording order
    """

    def __init__(self):
        self._events = ()
        self._lock = RLock()

    def record(
        self,
        event: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchAuditEvent,
    ) -> None:
        """
        Append an audit event to the log.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchAuditError:
                If event is None or its event ID is already recorded
        """

        if event is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchAuditError(
                "Cannot record a None branch audit event."
            )

        with self._lock:
            if any(existing.event_id == event.event_id for existing in self._events):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchAuditError(
                    f"Event ID {event.event_id!r} is already recorded."
                )

            self._events = self._events + (event,)

    def timeline(
        self,
        branch_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchTimeline:
        """
        Retrieve every audit event for a branch, in chronological
        order.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchAuditError:
                If branch_id is None or blank
        """

        self._validate_id(branch_id, "branch ID")

        with self._lock:
            matching = tuple(
                sorted(
                    (existing for existing in self._events if existing.branch_id == branch_id),
                    key=lambda existing: existing.timestamp,
                )
            )

        return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchTimeline(
            branch_id=branch_id,
            events=matching,
        )

    def latest(self, branch_id: str):
        """
        Retrieve the most recent audit event for a branch.

        Returns:
            The most recent audit event for branch_id, or None if no
            event has been recorded for it

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchAuditError:
                If branch_id is None or blank
        """

        self._validate_id(branch_id, "branch ID")

        with self._lock:
            matching = [existing for existing in self._events if existing.branch_id == branch_id]

        if not matching:
            return None

        return max(matching, key=lambda existing: existing.timestamp)

    def events(self, branch_id: str, event_type: str) -> tuple:
        """
        Retrieve every audit event of a given type for a branch, in
        chronological order.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchAuditError:
                If branch_id or event_type is None or blank, or
                event_type is not a recognized event type
        """

        self._validate_id(branch_id, "branch ID")

        if event_type is None or not event_type.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchAuditError(
                "Cannot filter branch audit events with an empty or blank event type."
            )

        if event_type not in _VALID_EVENT_TYPES:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchAuditError(
                f"Invalid branch audit event type {event_type!r}. Must be one of {_VALID_EVENT_TYPES!r}."
            )

        with self._lock:
            return tuple(
                sorted(
                    (
                        existing
                        for existing in self._events
                        if existing.branch_id == branch_id and existing.event_type == event_type
                    ),
                    key=lambda existing: existing.timestamp,
                )
            )

    def list(self) -> tuple:
        """
        List every recorded audit event, in chronological order.
        """

        with self._lock:
            return tuple(sorted(self._events, key=lambda existing: existing.timestamp))

    def purge(self, before_timestamp) -> int:
        """
        Remove every audit event older than before_timestamp.

        Args:
            before_timestamp: Events with a timestamp strictly earlier
                than this are removed; events at or after this
                timestamp are preserved

        Returns:
            The number of audit events removed

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchAuditError:
                If before_timestamp is None
        """

        if before_timestamp is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchAuditError(
                "Cannot purge with a None timestamp."
            )

        with self._lock:
            retained = tuple(existing for existing in self._events if existing.timestamp >= before_timestamp)

            purged_count = len(self._events) - len(retained)

            self._events = retained

            return purged_count

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceBranchAuditError(
                f"Cannot perform a branch audit lookup with an empty or blank {label}."
            )
