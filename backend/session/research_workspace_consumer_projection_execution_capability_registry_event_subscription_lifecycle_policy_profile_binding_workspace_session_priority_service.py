from threading import (
    RLock,
)

from typing import Optional

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_priority_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPriorityError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_priority import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPriority,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_priority_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPriorityResult,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPriorityService:
    """
    Orders ready consumer projection execution capability registry
    event subscription lifecycle policy profile binding workspace
    execution sessions for dispatch, so higher-priority work executes
    first without letting a steady stream of high-priority arrivals
    starve everything behind them.

    The service's responsibility is ordering only, not execution. It
    does NOT dispatch a session itself; a caller, such as the session
    scheduler, is expected to call next() to select which session to
    dispatch.

    Behavior:
    - A session's effective priority starts at its assigned base
      priority; update() and rebalance() are the only ways it
      changes, each applying one aging step to a session with
      aging_enabled set
    - Sessions are ordered by effective priority, highest first; ties
      are broken by assignment order, earliest first, so equal
      priority sessions execute FIFO
    - assign() re-registers a session already known to it in place,
      resetting its effective priority to the new base priority
      without changing its position in FIFO order
    - next() only peeks at the session that would execute next; it
      does not remove or otherwise consume it

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, aging_increment: float = 1.0):
        """
        Args:
            aging_increment: How much a session's effective priority
                rises per aging step applied through update() or
                rebalance(), when its aging_enabled is set

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPriorityError:
                If aging_increment is not a positive number
        """

        if (
            aging_increment is None
            or isinstance(aging_increment, bool)
            or not isinstance(aging_increment, (int, float))
            or aging_increment <= 0
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPriorityError(
                "Cannot build a session priority service with a non-positive aging_increment."
            )

        self._aging_increment = aging_increment
        self._priorities = {}
        self._effective = {}
        self._order = []
        self._lock = RLock()

    def assign(
        self,
        session_id: str,
        priority: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPriority,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPriority:
        """
        Assign a session its base priority, registering it for
        ordering, or re-registering it in place if already known.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPriorityError:
                If session_id is None or blank, or priority is not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPriority
                belonging to session_id
        """

        self._validate_id(session_id, "session ID")

        if not isinstance(priority, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPriority):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPriorityError(
                "Cannot assign an invalid priority: priority must be a "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPriority."
            )

        if priority.session_id != session_id:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPriorityError(
                f"Cannot assign a priority for session ID {priority.session_id!r} on behalf of session ID "
                f"{session_id!r}."
            )

        with self._lock:
            self._priorities[session_id] = priority
            self._effective[session_id] = float(priority.priority)

            if session_id not in self._order:
                self._order.append(session_id)

            return priority

    def update(self, session_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPriorityResult:
        """
        Apply one aging step to a single session, if its
        aging_enabled is set, and report its resulting standing.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPriorityError:
                If session_id is None or blank, or no priority is
                registered under it
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            priority = self._resolve(session_id)

            if priority.aging_enabled:
                self._effective[session_id] += self._aging_increment

            return self._result_for(session_id)

    def rebalance(self) -> tuple:
        """
        Apply one aging step to every session with aging_enabled set,
        then report every tracked session's resulting standing.

        Returns:
            A
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPriorityResult
            for every tracked session, in current execution order
        """

        with self._lock:
            for session_id in self._order:
                if self._priorities[session_id].aging_enabled:
                    self._effective[session_id] += self._aging_increment

            return tuple(self._result_for(session_id) for session_id in self._ordering())

    def next(self) -> Optional[ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPriority]:
        """
        Look up the session that would execute next: the highest
        effective priority, ties broken FIFO.

        Returns:
            The
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPriority
            of the session that would execute next, or None if no
            session is tracked
        """

        with self._lock:
            ordering = self._ordering()

            if not ordering:
                return None

            return self._priorities[ordering[0]]

    def effective(self, session_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPriorityResult:
        """
        Look up a session's current standing without changing it.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPriorityError:
                If session_id is None or blank, or no priority is
                registered under it
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            self._resolve(session_id)

            return self._result_for(session_id)

    def _ordering(self) -> list:
        return sorted(
            self._order,
            key=lambda session_id: (-self._effective[session_id], self._order.index(session_id)),
        )

    def _result_for(self, session_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPriorityResult:
        ordering = self._ordering()

        return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPriorityResult(
            execution_order=ordering.index(session_id),
            effective_priority=self._effective[session_id],
        )

    def _resolve(self, session_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPriority:
        priority = self._priorities.get(session_id)

        if priority is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPriorityError(
                f"No session priority is registered under session ID {session_id!r}."
            )

        return priority

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPriorityError(
                f"Cannot operate with an empty or blank {label}."
            )
