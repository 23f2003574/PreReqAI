from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from typing import Optional

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_scheduling_window_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingWindowError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_scheduling_window import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingWindow,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_window_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionWindowResult,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingWindowService:
    """
    Restricts consumer projection execution capability registry event
    subscription lifecycle policy profile binding workspace session
    schedules to their approved scheduling windows, so a schedule can
    only run inside a window it was explicitly assigned, and
    automatically defers to whichever valid window comes next when it
    cannot.

    The service's responsibility is window bookkeeping and
    time-based eligibility, not execution itself. It does NOT select
    or trigger a schedule for execution; a caller, such as the
    session scheduler, is expected to call validate() before
    dispatching a schedule for execution.

    Behavior:
    - A schedule may have any number of windows assigned to it;
      execution is eligible whenever the current instant falls inside
      any one of them
    - Every comparison is made against timezone-aware instants, so
      windows expressed in different time zones are evaluated
      correctly against one another regardless of which zone "now"
      is read in
    - defer() always looks strictly beyond the current instant, so it
      reports the next window still to come even while a schedule is
      already inside an active one
    - next_window() and active() are computed fresh from the current
      instant on every call

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self):
        self._windows = {}
        self._window_ids_by_schedule_id = {}
        self._lock = RLock()

    def assign(
        self,
        schedule_id: str,
        window: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingWindow,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingWindow:
        """
        Assign an approved scheduling window to a schedule.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingWindowError:
                If schedule_id is None or blank, window is not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingWindow
                belonging to schedule_id, or the window ID is already
                registered
        """

        self._validate_id(schedule_id, "schedule ID")

        if not isinstance(window, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingWindow):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingWindowError(
                "Cannot assign an invalid window: window must be a "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingWindow."
            )

        if window.schedule_id != schedule_id:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingWindowError(
                f"Cannot assign a window for schedule ID {window.schedule_id!r} on behalf of schedule ID "
                f"{schedule_id!r}."
            )

        with self._lock:
            if window.window_id in self._windows:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingWindowError(
                    f"Window ID {window.window_id!r} is already registered."
                )

            self._windows[window.window_id] = window
            self._window_ids_by_schedule_id.setdefault(schedule_id, []).append(window.window_id)

            return window

    def validate(self, schedule_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionWindowResult:
        """
        Check whether a schedule currently falls within one of its
        approved scheduling windows.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingWindowError:
                If schedule_id is None or blank
        """

        self._validate_id(schedule_id, "schedule ID")

        with self._lock:
            now = datetime.now(timezone.utc)
            windows = self._ordered_windows(schedule_id)

            if any(window.start_time <= now <= window.end_time for window in windows):
                return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionWindowResult(
                    executable=True,
                    next_window=None,
                )

            upcoming = self._soonest_after(windows, now)

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionWindowResult(
                executable=False,
                next_window=upcoming.start_time if upcoming is not None else None,
            )

    def next_window(self, schedule_id: str):
        """
        Look up the window governing a schedule's execution next: the
        one currently active, or the soonest one still to come.

        Returns:
            The
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingWindow
            with the earliest start_time among windows that have not
            yet closed, or None if none remain

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingWindowError:
                If schedule_id is None or blank
        """

        self._validate_id(schedule_id, "schedule ID")

        with self._lock:
            now = datetime.now(timezone.utc)
            open_windows = tuple(window for window in self._ordered_windows(schedule_id) if window.end_time > now)

            if not open_windows:
                return None

            return min(open_windows, key=lambda window: window.start_time)

    def defer(self, schedule_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionWindowResult:
        """
        Defer a schedule to its next valid window, strictly beyond
        the current instant even if a window is already active.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingWindowError:
                If schedule_id is None or blank
        """

        self._validate_id(schedule_id, "schedule ID")

        with self._lock:
            now = datetime.now(timezone.utc)
            upcoming = self._soonest_after(self._ordered_windows(schedule_id), now)

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionWindowResult(
                executable=False,
                next_window=upcoming.start_time if upcoming is not None else None,
            )

    def active(self) -> tuple:
        """
        List every schedule ID currently inside one of its approved
        scheduling windows.
        """

        with self._lock:
            now = datetime.now(timezone.utc)

            return tuple(
                schedule_id
                for schedule_id in self._window_ids_by_schedule_id
                if any(window.start_time <= now <= window.end_time for window in self._ordered_windows(schedule_id))
            )

    def _ordered_windows(self, schedule_id: str) -> tuple:
        return tuple(
            self._windows[window_id] for window_id in self._window_ids_by_schedule_id.get(schedule_id, ())
        )

    def _soonest_after(self, windows: tuple, now: datetime) -> Optional[ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingWindow]:
        future = tuple(window for window in windows if window.start_time > now)

        if not future:
            return None

        return min(future, key=lambda window: window.start_time)

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingWindowError(
                f"Cannot operate with an empty or blank {label}."
            )
