from dataclasses import (
    dataclass,
)

from datetime import (
    date,
    datetime,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_scheduling_constraint_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingConstraintError,
)

VALID_SESSION_SCHEDULING_CONSTRAINT_TYPES = frozenset(
    {
        "capacity",
        "maintenance",
        "holiday",
        "predicate",
    }
)

_CONFIGURATION_KEYS_BY_TYPE = {
    "capacity": frozenset({"current", "limit"}),
    "maintenance": frozenset({"start", "end"}),
    "holiday": frozenset({"dates"}),
    "predicate": frozenset({"predicate"}),
}


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingConstraint:
    """
    Immutable, reusable rule a consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding workspace session schedule must satisfy before it becomes
    runnable: a capacity limit, a maintenance window, a holiday
    calendar, or a custom predicate.

    The constraint is a value object only. It performs no evaluation.
    Registering, assigning, evaluating, enabling, and disabling
    constraints is the responsibility of a session scheduling
    constraint service.

    Attributes:
        constraint_id: The constraint's unique identifier
        type: The kind of constraint this is; one of "capacity",
            "maintenance", "holiday", or "predicate"
        configuration: A mapping whose required keys depend on type:
            - "capacity": {"current": int, "limit": int}; satisfied
              when current is strictly less than limit
            - "maintenance": {"start": datetime, "end": datetime},
              both timezone-aware and end strictly after start;
              satisfied when the current instant falls outside
              [start, end]
            - "holiday": {"dates": frozenset of date}; satisfied when
              the current UTC date is not among dates
            - "predicate": {"predicate": callable}; satisfied when
              calling predicate(schedule_id) returns a truthy value
        enabled: Whether this constraint is currently evaluated;
            evaluate() skips a disabled constraint entirely
    """

    constraint_id: str

    type: str

    configuration: dict

    enabled: bool

    def __post_init__(self):
        if self.constraint_id is None or not self.constraint_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingConstraintError(
                "Cannot build a session scheduling constraint with an empty or blank constraint ID."
            )

        if self.type not in VALID_SESSION_SCHEDULING_CONSTRAINT_TYPES:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingConstraintError(
                f"Cannot build a session scheduling constraint with unknown type {self.type!r}; expected one of "
                f"{sorted(VALID_SESSION_SCHEDULING_CONSTRAINT_TYPES)}."
            )

        if self.enabled is None or not isinstance(self.enabled, bool):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingConstraintError(
                "Cannot build a session scheduling constraint with a non-boolean enabled."
            )

        self._validate_configuration()

    def _validate_configuration(self) -> None:
        error = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingConstraintError

        if not isinstance(self.configuration, dict) or set(self.configuration.keys()) != _CONFIGURATION_KEYS_BY_TYPE[self.type]:
            raise error(
                f"Cannot build a {self.type!r} session scheduling constraint with configuration that is not a "
                f"dict with exactly the keys {sorted(_CONFIGURATION_KEYS_BY_TYPE[self.type])}."
            )

        if self.type == "capacity":
            current = self.configuration["current"]
            limit = self.configuration["limit"]

            if not isinstance(current, int) or isinstance(current, bool) or current < 0:
                raise error("Cannot build a capacity constraint with a non-negative-integer current.")

            if not isinstance(limit, int) or isinstance(limit, bool) or limit < 0:
                raise error("Cannot build a capacity constraint with a non-negative-integer limit.")

        elif self.type == "maintenance":
            start = self.configuration["start"]
            end = self.configuration["end"]

            if not isinstance(start, datetime) or start.utcoffset() is None:
                raise error("Cannot build a maintenance constraint with a non-timezone-aware start.")

            if not isinstance(end, datetime) or end.utcoffset() is None:
                raise error("Cannot build a maintenance constraint with a non-timezone-aware end.")

            if end <= start:
                raise error("Cannot build a maintenance constraint with end at or before start.")

        elif self.type == "holiday":
            dates = self.configuration["dates"]

            if not isinstance(dates, frozenset) or not all(
                isinstance(entry, date) and not isinstance(entry, datetime) for entry in dates
            ):
                raise error("Cannot build a holiday constraint with dates that is not a frozenset of date.")

        elif self.type == "predicate":
            if not callable(self.configuration["predicate"]):
                raise error("Cannot build a predicate constraint with a non-callable predicate.")
