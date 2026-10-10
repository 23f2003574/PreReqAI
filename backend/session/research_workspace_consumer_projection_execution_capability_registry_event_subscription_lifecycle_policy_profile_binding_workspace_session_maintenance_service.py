from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_maintenance_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionMaintenanceError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_maintenance_window import (
    GLOBAL_MAINTENANCE_SCOPE,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionMaintenanceWindow,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_maintenance_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionMaintenanceResult,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionMaintenanceService:
    """
    Pauses consumer projection execution capability registry event
    subscription lifecycle policy profile binding workspace session
    dispatch during maintenance windows, resuming it automatically
    once every globally-scoped window has passed.

    The service's responsibility is gating new dispatch, not the
    sessions already queued elsewhere. It does NOT track, hold, or
    otherwise touch queued sessions; a caller, such as the session
    scheduler, is expected to call suspend() before dispatching and
    resume() to check whether it may proceed again. Sessions already
    queued upstream of that check are left entirely alone: suspending
    dispatch only withholds new dispatch decisions, it never inspects
    or discards what is already waiting.

    Behavior:
    - Only a window with scope "global" pauses dispatch; a
      narrower-scoped window is tracked and reported through active()
      but never causes suspend() to pause dispatch on its own
    - suspend() pauses dispatch the moment any global window is
      currently active, and stays paused on every later call for as
      long as one remains active
    - resume() only lifts the pause once no global window remains
      active, reporting resumed exactly on the call that lifts it
    - active() is computed fresh from the current instant on every
      call, so a window past its ends_at stops appearing in it, and
      stops counting toward suspend(), automatically

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self):
        self._windows = {}
        self._suspended = False
        self._lock = RLock()

    def enable(
        self,
        window: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionMaintenanceWindow,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionMaintenanceWindow:
        """
        Enable a maintenance window.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionMaintenanceError:
                If window is not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionMaintenanceWindow,
                or its window ID is already registered
        """

        if not isinstance(window, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionMaintenanceWindow):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionMaintenanceError(
                "Cannot enable an invalid window: window must be a "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionMaintenanceWindow."
            )

        with self._lock:
            if window.window_id in self._windows:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionMaintenanceError(
                    f"Window ID {window.window_id!r} is already registered."
                )

            self._windows[window.window_id] = window

            return window

    def disable(self, window_id: str) -> None:
        """
        Disable a maintenance window immediately.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionMaintenanceError:
                If window_id is None or blank, or no window is
                registered under it
        """

        self._validate_id(window_id, "window ID")

        with self._lock:
            if window_id not in self._windows:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionMaintenanceError(
                    f"No session maintenance window is registered under window ID {window_id!r}."
                )

            del self._windows[window_id]

    def active(self) -> tuple:
        """
        List every maintenance window currently open, of any scope.
        """

        with self._lock:
            now = datetime.now(timezone.utc)

            return tuple(window for window in self._windows.values() if window.starts_at <= now <= window.ends_at)

    def suspend(self) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionMaintenanceResult:
        """
        Pause dispatch if a global maintenance window is currently
        active.
        """

        with self._lock:
            if self._global_window_active_locked():
                self._suspended = True

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionMaintenanceResult(
                suspended=self._suspended,
                resumed=False,
            )

    def resume(self) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionMaintenanceResult:
        """
        Lift dispatch's pause once no global maintenance window
        remains active.
        """

        with self._lock:
            if self._suspended and not self._global_window_active_locked():
                self._suspended = False

                return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionMaintenanceResult(
                    suspended=False,
                    resumed=True,
                )

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionMaintenanceResult(
                suspended=self._suspended,
                resumed=False,
            )

    def _global_window_active_locked(self) -> bool:
        now = datetime.now(timezone.utc)

        return any(
            window.scope == GLOBAL_MAINTENANCE_SCOPE and window.starts_at <= now <= window.ends_at
            for window in self._windows.values()
        )

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionMaintenanceError(
                f"Cannot operate with an empty or blank {label}."
            )
