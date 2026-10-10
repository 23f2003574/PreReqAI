from dataclasses import replace

from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_scheduling_constraint_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingConstraintError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_scheduling_constraint import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingConstraint,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_constraint_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionConstraintResult,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingConstraintService:
    """
    Gates consumer projection execution capability registry event
    subscription lifecycle policy profile binding workspace session
    schedules behind reusable scheduling constraints, so a schedule
    only becomes runnable once every constraint assigned to it,
    capacity limits, maintenance windows, holiday calendars, or
    custom predicates alike, is satisfied.

    The service's responsibility is constraint bookkeeping and
    evaluation, not execution itself. It does NOT select or trigger a
    schedule for execution; a caller, such as the session scheduler,
    is expected to call evaluate() before dispatching a schedule for
    execution.

    Behavior:
    - A constraint is registered once, independent of any schedule,
      and may then be assigned to any number of schedules; a schedule
      may likewise have any number of constraints assigned to it
    - evaluate() only ever considers a schedule's assigned constraints
      that are currently enabled; a disabled constraint is skipped
      entirely
    - evaluate() checks a schedule's enabled constraints in the order
      they were assigned and stops at the first violation it finds,
      so violations holds at most one entry
    - enable() and disable() take effect immediately: a constraint
      already assigned to schedules is toggled everywhere it is used

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self):
        self._constraints = {}
        self._constraint_order = []
        self._constraint_ids_by_schedule_id = {}
        self._lock = RLock()

    def register(
        self,
        constraint: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingConstraint,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingConstraint:
        """
        Register a reusable constraint.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingConstraintError:
                If constraint is not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingConstraint,
                or its constraint ID is already registered
        """

        if not isinstance(constraint, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingConstraint):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingConstraintError(
                "Cannot register an invalid constraint: constraint must be a "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingConstraint."
            )

        with self._lock:
            if constraint.constraint_id in self._constraints:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingConstraintError(
                    f"Constraint ID {constraint.constraint_id!r} is already registered."
                )

            self._constraints[constraint.constraint_id] = constraint
            self._constraint_order.append(constraint.constraint_id)

            return constraint

    def assign(self, schedule_id: str, constraint_id: str) -> None:
        """
        Assign a registered constraint to a schedule.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingConstraintError:
                If schedule_id or constraint_id is None or blank, no
                constraint is registered under constraint_id, or it is
                already assigned to schedule_id
        """

        self._validate_id(schedule_id, "schedule ID")
        self._validate_id(constraint_id, "constraint ID")

        with self._lock:
            self._resolve(constraint_id)

            assigned = self._constraint_ids_by_schedule_id.setdefault(schedule_id, [])

            if constraint_id in assigned:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingConstraintError(
                    f"Constraint ID {constraint_id!r} is already assigned to schedule ID {schedule_id!r}."
                )

            assigned.append(constraint_id)

    def evaluate(self, schedule_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionConstraintResult:
        """
        Check whether a schedule currently satisfies every enabled
        constraint assigned to it, stopping at the first violation.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingConstraintError:
                If schedule_id is None or blank
        """

        self._validate_id(schedule_id, "schedule ID")

        with self._lock:
            for constraint_id in self._constraint_ids_by_schedule_id.get(schedule_id, ()):
                constraint = self._constraints[constraint_id]

                if not constraint.enabled:
                    continue

                if not self._is_satisfied(constraint, schedule_id):
                    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionConstraintResult(
                        satisfied=False,
                        violations=(constraint_id,),
                    )

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionConstraintResult(
                satisfied=True,
                violations=(),
            )

    def enable(
        self,
        constraint_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingConstraint:
        """
        Enable a constraint, so evaluate() considers it again.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingConstraintError:
                If constraint_id is None or blank, or no constraint is
                registered under it
        """

        return self._set_enabled(constraint_id, True)

    def disable(
        self,
        constraint_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingConstraint:
        """
        Disable a constraint, so evaluate() skips it entirely.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingConstraintError:
                If constraint_id is None or blank, or no constraint is
                registered under it
        """

        return self._set_enabled(constraint_id, False)

    def _set_enabled(
        self,
        constraint_id: str,
        enabled: bool,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingConstraint:
        self._validate_id(constraint_id, "constraint ID")

        with self._lock:
            constraint = self._resolve(constraint_id)

            updated = replace(constraint, enabled=enabled)

            self._constraints[constraint_id] = updated

            return updated

    def _is_satisfied(
        self,
        constraint: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingConstraint,
        schedule_id: str,
    ) -> bool:
        configuration = constraint.configuration

        if constraint.type == "capacity":
            return configuration["current"] < configuration["limit"]

        if constraint.type == "maintenance":
            now = datetime.now(timezone.utc)
            return not (configuration["start"] <= now <= configuration["end"])

        if constraint.type == "holiday":
            today = datetime.now(timezone.utc).date()
            return today not in configuration["dates"]

        return bool(configuration["predicate"](schedule_id))

    def _resolve(
        self,
        constraint_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingConstraint:
        constraint = self._constraints.get(constraint_id)

        if constraint is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingConstraintError(
                f"No session scheduling constraint is registered under constraint ID {constraint_id!r}."
            )

        return constraint

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingConstraintError(
                f"Cannot operate with an empty or blank {label}."
            )
