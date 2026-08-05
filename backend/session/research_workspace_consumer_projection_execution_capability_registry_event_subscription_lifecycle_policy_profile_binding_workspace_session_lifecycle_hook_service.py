from dataclasses import (
    replace,
)

from threading import (
    RLock,
)

from time import perf_counter

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_lifecycle_hook_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLifecycleHookError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_lifecycle_hook import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLifecycleHook,
    VALID_SESSION_LIFECYCLE_HOOK_EVENTS,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_hook_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionHookResult,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLifecycleHookService:
    """
    Runs custom logic at key consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    workspace execution session lifecycle events — START, FINISH,
    CANCEL, and RESTORE — so callers can extend session behavior
    without modifying the session engine that emits those events.

    The service's responsibility is hook registration and dispatch,
    not session execution. It does NOT emit lifecycle events itself;
    it assumes the execution session engine already does, and expects
    a caller to invoke execute(event, session_id) at the moment each
    event actually occurs.

    Behavior:
    - Hooks registered for the same event run in the order they were
      registered
    - A disabled hook is skipped entirely; it never appears in
      execute()'s results
    - A handler that raises does not stop other hooks for the same
      event from running, and does not propagate out of execute();
      it is reported as an unsuccessful ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionHookResult
      instead

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self):
        self._hooks_by_id = {}
        self._hook_ids_by_event = {}
        self._lock = RLock()

    def register(self, hook: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLifecycleHook) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLifecycleHook:
        """
        Register a new lifecycle hook.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLifecycleHookError:
                If hook is not a ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLifecycleHook,
                or its hook ID is already registered
        """

        if not isinstance(hook, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLifecycleHook):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLifecycleHookError(
                "Cannot register an invalid session lifecycle hook: hook must be a "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLifecycleHook."
            )

        with self._lock:
            if hook.hook_id in self._hooks_by_id:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLifecycleHookError(
                    f"Hook ID {hook.hook_id!r} is already registered."
                )

            self._hooks_by_id[hook.hook_id] = hook
            self._hook_ids_by_event.setdefault(hook.event, []).append(hook.hook_id)

            return hook

    def enable(self, hook_id: str) -> None:
        """
        Enable a registered hook, so it runs the next time its event
        fires.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLifecycleHookError:
                If hook_id is None or blank, or no hook is registered
                under it
        """

        self._validate_id(hook_id, "hook ID")

        with self._lock:
            hook = self._resolve(hook_id)

            self._hooks_by_id[hook_id] = replace(hook, enabled=True)

    def disable(self, hook_id: str) -> None:
        """
        Disable a registered hook, so it is skipped the next time its
        event fires.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLifecycleHookError:
                If hook_id is None or blank, or no hook is registered
                under it
        """

        self._validate_id(hook_id, "hook ID")

        with self._lock:
            hook = self._resolve(hook_id)

            self._hooks_by_id[hook_id] = replace(hook, enabled=False)

    def execute(self, event: str, session_id: str) -> tuple:
        """
        Run every enabled hook registered for an event, in
        registration order.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLifecycleHookError:
                If event is not one of "START", "FINISH", "CANCEL", or
                "RESTORE", or session_id is None or blank
        """

        self._validate_event(event)
        self._validate_id(session_id, "session ID")

        with self._lock:
            hook_ids = list(self._hook_ids_by_event.get(event, []))
            hooks = [self._hooks_by_id[hook_id] for hook_id in hook_ids if self._hooks_by_id[hook_id].enabled]

        results = []

        for hook in hooks:
            started_at = perf_counter()
            executed = True

            try:
                hook.handler(session_id)
            except Exception:
                executed = False

            duration_ms = (perf_counter() - started_at) * 1000

            results.append(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionHookResult(
                    hook_id=hook.hook_id,
                    executed=executed,
                    duration_ms=duration_ms,
                )
            )

        return tuple(results)

    def hooks(self, event: str) -> tuple:
        """
        List every hook registered for an event, enabled or not, in
        registration order.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLifecycleHookError:
                If event is not one of "START", "FINISH", "CANCEL", or
                "RESTORE"
        """

        self._validate_event(event)

        with self._lock:
            return tuple(self._hooks_by_id[hook_id] for hook_id in self._hook_ids_by_event.get(event, []))

    def _resolve(self, hook_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLifecycleHook:
        hook = self._hooks_by_id.get(hook_id)

        if hook is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLifecycleHookError(
                f"No session lifecycle hook is registered under hook ID {hook_id!r}."
            )

        return hook

    def _validate_event(self, event: str) -> None:
        if event is None or not isinstance(event, str) or not event.strip() or event not in VALID_SESSION_LIFECYCLE_HOOK_EVENTS:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLifecycleHookError(
                f"Invalid session lifecycle hook event {event!r}. Must be one of "
                f"{VALID_SESSION_LIFECYCLE_HOOK_EVENTS!r}."
            )

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLifecycleHookError(
                f"Cannot operate with an empty or blank {label}."
            )
