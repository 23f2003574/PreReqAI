from threading import (
    RLock,
)

from types import MappingProxyType

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_assignment import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignment,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_assignment_registry import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRegistry,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_assignment_registry_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRegistryError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_assignment_registry_snapshot import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRegistrySnapshot,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRegistryService:
    """
    Maintains a centralised registry of active consumer projection
    execution capability registry event subscription lifecycle policy
    profile assignments, addressed by target identifier.

    The service's responsibility is assignment registration,
    replacement, removal, lookup, containment checking, listing, and
    snapshot generation, not profile validation, versioning, policy
    evaluation, lifecycle transition execution, persistence, logging,
    or event publication. It does NOT validate assignments, publish
    versions, evaluate policies, execute lifecycle transitions,
    persist the registry, log, or publish events.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    - Duplicate-free: No two active assignments may share a target ID
    - Order-preserving: Assignments are listed in the order they were
      first registered
    - Immutable registry: The underlying registry value object is
      replaced atomically on every mutation rather than mutated in
      place
    """

    def __init__(self):

        self._registry = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRegistry(
                assignments=MappingProxyType({})
            )
        )

        self._lock = RLock()

    def register(

        self,

        assignment,

    ) -> None:
        """
        Register an active profile assignment.

        Args:
            assignment: The assignment to register

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRegistryError:
                If the assignment is None, not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignment,
                has an empty or blank target ID, or its target ID is
                already registered
        """

        self._validate_assignment(
            assignment
        )

        with self._lock:

            if assignment.target_id in self._registry.assignments:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRegistryError(
                        "Cannot register an assignment: target ID "
                        f"{assignment.target_id!r} is already registered."
                    )
                )

            updated = dict(
                self._registry.assignments
            )

            updated[assignment.target_id] = assignment

            self._replace_assignments(
                updated
            )

    def replace(

        self,

        assignment,

    ) -> None:
        """
        Replace an already-registered profile assignment.

        The replaced assignment keeps its original position in
        registration order.

        Args:
            assignment: The assignment to replace the existing one
                with

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRegistryError:
                If the assignment is None, not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignment,
                has an empty or blank target ID, or no assignment is
                registered under its target ID
        """

        self._validate_assignment(
            assignment
        )

        with self._lock:

            if assignment.target_id not in self._registry.assignments:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRegistryError(
                        "Cannot replace an assignment: no assignment is "
                        f"registered under target ID {assignment.target_id!r}."
                    )
                )

            updated = dict(
                self._registry.assignments
            )

            updated[assignment.target_id] = assignment

            self._replace_assignments(
                updated
            )

    def remove(

        self,

        target_id,

    ) -> None:
        """
        Remove the assignment registered under a target ID.

        Unlike a plain deletion, removing a target ID that was never
        registered is rejected rather than treated as a no-op.

        Args:
            target_id: The target ID whose assignment should be
                removed

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRegistryError:
                If the target ID is None or blank, or no assignment is
                registered under it
        """

        self._validate_target_id(
            target_id
        )

        with self._lock:

            if target_id not in self._registry.assignments:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRegistryError(
                        "Cannot remove an assignment: no assignment is "
                        f"registered under target ID {target_id!r}."
                    )
                )

            updated = dict(
                self._registry.assignments
            )

            del updated[target_id]

            self._replace_assignments(
                updated
            )

    def find(

        self,

        target_id,

    ):
        """
        Find the assignment registered under a target ID.

        Args:
            target_id: The target ID to look up

        Returns:
            The matching assignment, or None if no assignment is
            registered under it
        """

        with self._lock:

            return self._registry.assignments.get(
                target_id
            )

    def contains(

        self,

        target_id,

    ) -> bool:
        """
        Check whether an assignment is registered under a target ID.

        Args:
            target_id: The target ID to check

        Returns:
            True if an assignment is registered under the target ID,
            False otherwise
        """

        with self._lock:

            return target_id in self._registry.assignments

    def list(

        self,

    ) -> tuple:
        """
        List every registered assignment.

        Returns:
            An immutable tuple of every registered assignment,
            preserving registration order
        """

        with self._lock:

            return tuple(
                self._registry.assignments.values()
            )

    def snapshot(

        self,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRegistrySnapshot:
        """
        Take a snapshot of the registry's current state.

        Returns:
            An immutable snapshot carrying the current assignment
            count, every registered target identifier, and every
            corresponding profile identifier, all preserving
            registration order
        """

        with self._lock:

            assignments = self._registry.assignments

            return (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRegistrySnapshot(
                    assignment_count=len(
                        assignments
                    ),

                    target_ids=tuple(
                        assignments.keys()
                    ),

                    profile_ids=tuple(
                        a.profile_id
                        for a in assignments.values()
                    ),
                )
            )

    def _replace_assignments(

        self,

        assignments,

    ) -> None:

        self._registry = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRegistry(
                assignments=MappingProxyType(
                    assignments
                )
            )
        )

    def _validate_target_id(

        self,

        target_id,

    ) -> None:

        if (

            target_id is None

            or not target_id.strip()
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRegistryError(
                    "Cannot operate on an assignment with an empty or blank "
                    "target ID."
                )
            )

    def _validate_assignment(

        self,

        assignment,

    ) -> None:

        if assignment is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRegistryError(
                    "Cannot register a None assignment."
                )
            )

        if not isinstance(

            assignment,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignment,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentRegistryError(
                    "Cannot register an assignment: assignment must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignment."
                )
            )

        self._validate_target_id(
            assignment.target_id
        )
