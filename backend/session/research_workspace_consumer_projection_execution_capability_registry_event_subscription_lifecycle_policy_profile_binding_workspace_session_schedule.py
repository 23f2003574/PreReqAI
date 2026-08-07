from dataclasses import (
    dataclass,
)

from datetime import (
    datetime,
    timedelta,
)

from typing import Optional

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_schedule_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleError,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedule:
    """
    Immutable reusable plan for when a consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding workspace execution session should next run, so a session
    can be triggered in the future, or repeatedly, without a caller
    having to re-request it each time.

    The schedule is a value object only. It performs no triggering.
    Creating, advancing, and cancelling schedules is the
    responsibility of a session scheduler service.

    Attributes:
        schedule_id: The schedule's unique identifier
        session_id: The identifier of the execution session this
            schedule triggers
        trigger_at: When this schedule is next due to run
        recurrence: How long after trigger_at this schedule should
            next run again, or None if it triggers only once
        enabled: Whether this schedule is currently live; a disabled
            schedule is skipped by lookup, without being cancelled
    """

    schedule_id: str

    session_id: str

    trigger_at: datetime

    recurrence: Optional[timedelta]

    enabled: bool

    def __post_init__(self):
        if self.schedule_id is None or not self.schedule_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleError(
                "Cannot build a session schedule with an empty or blank schedule ID."
            )

        if self.session_id is None or not self.session_id.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleError(
                "Cannot build a session schedule with an empty or blank session ID."
            )

        if self.trigger_at is None or not isinstance(self.trigger_at, datetime):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleError(
                "Cannot build a session schedule with a non-datetime trigger_at."
            )

        if self.recurrence is not None:
            if not isinstance(self.recurrence, timedelta):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleError(
                    "Cannot build a session schedule with a non-timedelta recurrence."
                )

            if self.recurrence <= timedelta(0):
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleError(
                    "Cannot build a session schedule with a non-positive recurrence."
                )

        if self.enabled is None or not isinstance(self.enabled, bool):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionScheduleError(
                "Cannot build a session schedule with a non-boolean enabled."
            )
