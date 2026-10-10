from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_assignment import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignment,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_assignment_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_assignment_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResult,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentService:
    """
    Assigns registered consumer projection execution capability
    registry event subscription lifecycle policy profiles to
    capabilities, subscriptions, or execution contexts.

    The service's responsibility is profile-to-target assignment
    tracking, not profile registration, policy evaluation, or
    lifecycle transition execution. It does NOT register profiles,
    mutate an existing assignment record, persist assignments
    externally, log, or publish events. Every assignment produces a
    new, immutable assignment record; no assignment record is ever
    mutated.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    - One active assignment per target: Each target may have at most
      one currently active profile assignment
    - Duplicate-aware: assign() rejects assigning the same profile to
      a target that already has it actively assigned; assigning a
      different profile replaces the active mapping only
    """

    def __init__(

        self,

        profile_service,

    ):
        """
        Args:
            profile_service: The profile service used to verify a
                profile exists before it is assigned. Any object
                exposing `contains(profile_id)` is accepted
        """

        self._profile_service = profile_service

        self._records = ()

        self._active_by_target = {}

        self._sequence = 0

        self._lock = RLock()

    def assign(

        self,

        target_id,

        profile_id,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResult:
        """
        Assign a profile to a target.

        Args:
            target_id: The target to assign the profile to
            profile_id: The profile to assign

        Returns:
            An immutable assignment result carrying the new assignment
            record

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentError:
                If the target ID or profile ID is None or blank, no
                profile is registered under the profile ID, or the
                same profile is already actively assigned to the
                target
        """

        self._validate_identifier(
            target_id,

            "target ID",
        )

        self._validate_identifier(
            profile_id,

            "profile ID",
        )

        if not self._profile_service.contains(profile_id):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentError(
                    "Cannot assign a profile: no profile is registered "
                    f"under profile ID {profile_id!r}."
                )
            )

        with self._lock:

            active_assignment = self._active_assignment_for(
                target_id
            )

            if (

                active_assignment is not None

                and active_assignment.profile_id == profile_id
            ):

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentError(
                        "Cannot assign a profile: profile ID "
                        f"{profile_id!r} is already actively assigned to "
                        f"target ID {target_id!r}."
                    )
                )

            assignment = self._create_assignment(

                target_id,

                profile_id,
            )

            self._records = self._records + (assignment,)

            self._active_by_target[target_id] = assignment.assignment_id

            return (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResult(
                    assignment=assignment,

                    successful=True,
                )
            )

    def unassign(

        self,

        target_id,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResult:
        """
        Unassign the profile currently assigned to a target.

        Args:
            target_id: The target to unassign

        Returns:
            An immutable assignment result carrying the assignment
            record that was active before unassignment

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentError:
                If the target ID is None or blank, or no profile is
                actively assigned to the target
        """

        self._validate_identifier(
            target_id,

            "target ID",
        )

        with self._lock:

            active_assignment = self._active_assignment_for(
                target_id
            )

            if active_assignment is None:

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentError(
                        "Cannot unassign a profile: no profile is actively "
                        f"assigned to target ID {target_id!r}."
                    )
                )

            del self._active_by_target[target_id]

            return (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentResult(
                    assignment=active_assignment,

                    successful=True,
                )
            )

    def find(

        self,

        target_id,

    ):
        """
        Find the profile assignment currently active for a target.

        Args:
            target_id: The target ID to look up

        Returns:
            The active assignment for the target, or None if no
            profile is actively assigned to it
        """

        with self._lock:

            return self._active_assignment_for(
                target_id
            )

    def is_assigned(

        self,

        target_id,

    ) -> bool:
        """
        Check whether a target currently has an active profile
        assignment.

        Args:
            target_id: The target ID to check

        Returns:
            True if a profile is actively assigned to the target,
            False otherwise
        """

        with self._lock:

            return target_id in self._active_by_target

    def list(

        self,

    ) -> tuple:
        """
        List every assignment record.

        Returns:
            An immutable tuple of every assignment record, in the
            order they were created
        """

        with self._lock:

            return self._records

    def _active_assignment_for(

        self,

        target_id,

    ):

        assignment_id = self._active_by_target.get(
            target_id
        )

        if assignment_id is None:

            return None

        return self._find_record(
            assignment_id
        )

    def _find_record(

        self,

        assignment_id,

    ):

        for record in self._records:

            if record.assignment_id == assignment_id:

                return record

        return None

    def _create_assignment(

        self,

        target_id,

        profile_id,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignment:

        self._sequence += 1

        assigned_at = datetime.now(
            timezone.utc
        )

        assignment_id = self._generate_assignment_id(

            target_id,

            profile_id,

            self._sequence,
        )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignment(
                assignment_id=assignment_id,

                target_id=target_id,

                profile_id=profile_id,

                assigned_at=assigned_at,
            )
        )

    def _generate_assignment_id(

        self,

        target_id,

        profile_id,

        sequence,

    ) -> str:

        return f"{target_id}::{profile_id}::{sequence}"

    def _validate_identifier(

        self,

        identifier,

        label,

    ) -> None:

        if (

            identifier is None

            or not identifier.strip()
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileAssignmentError(
                    f"Cannot assign with an empty or blank {label}."
                )
            )
