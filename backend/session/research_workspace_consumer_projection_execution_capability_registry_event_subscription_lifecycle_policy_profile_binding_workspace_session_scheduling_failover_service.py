from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_scheduling_failover_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingFailoverError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_failover_plan import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionFailoverPlan,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_failover_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionFailoverResult,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingFailoverService:
    """
    Automatically reassigns consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    workspace execution sessions away from an execution worker that
    becomes unavailable before their execution begins, using each
    session's registered failover plan.

    The service's responsibility is worker-level failover only, not
    the initial placement itself; a session's primary and backup
    workers are assumed to already come from the existing session
    scheduler and load balancer. A caller, such as the load balancer,
    is expected to call failover() only after a worker assignment has
    already been made, once it learns that worker is unavailable.

    Behavior:
    - failover() is itself what marks a session's current worker
      unavailable: calling it is how the service learns a worker has
      gone down
    - Backup workers are tried in the order a plan lists them,
      skipping any that are currently unavailable; the first
      available one is chosen
    - recover() clears a worker's unavailable status, making it
      eligible again for future failovers
    - status() reports a session's current worker and whether it has
      been reassigned away from its plan's primary_worker, reflecting
      every failover decision recorded against it

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self):
        self._plans_by_id = {}
        self._plans_by_session_id = {}
        self._current_worker_by_session = {}
        self._unavailable_workers = set()
        self._lock = RLock()

    def register(
        self,
        plan: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionFailoverPlan,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionFailoverPlan:
        """
        Register a failover plan for a session.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingFailoverError:
                If plan is not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionFailoverPlan,
                or its plan ID or session ID is already registered
        """

        if not isinstance(plan, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionFailoverPlan):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingFailoverError(
                "Cannot register an invalid plan: plan must be a "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionFailoverPlan."
            )

        with self._lock:
            if plan.plan_id in self._plans_by_id:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingFailoverError(
                    f"Plan ID {plan.plan_id!r} is already registered."
                )

            if plan.session_id in self._plans_by_session_id:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingFailoverError(
                    f"Session ID {plan.session_id!r} already has a registered failover plan."
                )

            self._plans_by_id[plan.plan_id] = plan
            self._plans_by_session_id[plan.session_id] = plan
            self._current_worker_by_session[plan.session_id] = plan.primary_worker

            return plan

    def failover(self, session_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionFailoverResult:
        """
        Mark a session's current worker unavailable and reassign the
        session to the first available backup worker, in plan order.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingFailoverError:
                If session_id is None or blank, no failover plan is
                registered under it, or no backup worker is currently
                available
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            plan = self._resolve_plan(session_id)
            current_worker = self._current_worker_by_session[session_id]

            self._unavailable_workers.add(current_worker)

            for backup_worker in plan.backup_workers:
                if backup_worker not in self._unavailable_workers:
                    self._current_worker_by_session[session_id] = backup_worker

                    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionFailoverResult(
                        reassigned=True,
                        worker_id=backup_worker,
                    )

            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingFailoverError(
                f"Cannot fail over session ID {session_id!r}: no backup worker is currently available."
            )

    def available(self, worker_id: str) -> bool:
        """
        Check whether an execution worker is currently available.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingFailoverError:
                If worker_id is None or blank
        """

        self._validate_id(worker_id, "worker ID")

        with self._lock:
            return worker_id not in self._unavailable_workers

    def recover(self, worker_id: str) -> None:
        """
        Clear an execution worker's unavailable status.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingFailoverError:
                If worker_id is None or blank
        """

        self._validate_id(worker_id, "worker ID")

        with self._lock:
            self._unavailable_workers.discard(worker_id)

    def status(self, session_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionFailoverResult:
        """
        Look up a session's current worker and whether it has been
        reassigned away from its plan's primary_worker.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingFailoverError:
                If session_id is None or blank, or no failover plan is
                registered under it
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            plan = self._resolve_plan(session_id)
            current_worker = self._current_worker_by_session[session_id]

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionFailoverResult(
                reassigned=current_worker != plan.primary_worker,
                worker_id=current_worker,
            )

    def _resolve_plan(
        self,
        session_id: str,
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionFailoverPlan:
        plan = self._plans_by_session_id.get(session_id)

        if plan is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingFailoverError(
                f"No failover plan is registered for session ID {session_id!r}."
            )

        return plan

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingFailoverError(
                f"Cannot operate with an empty or blank {label}."
            )
