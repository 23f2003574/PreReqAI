from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_scheduling_balancer_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingBalancerError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_scheduling_strategy import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingStrategy,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_scheduling_assignment import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingAssignment,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingBalancerService:
    """
    Distributes consumer projection execution capability registry
    event subscription lifecycle policy profile binding workspace
    execution sessions across a fixed pool of execution workers, so
    load stays even and no single worker is driven past its capacity.

    The service's responsibility is worker placement, not execution
    itself. It does NOT dispatch a session for execution; a caller,
    such as the session scheduler, is expected to call assign() only
    after a schedule has already been selected for dispatch.

    Behavior:
    - assign() places a session on a worker using the configured,
      active strategy's algorithm, considering only workers currently
      under capacity
    - rebalance() recomputes every currently tracked session's
      placement from scratch, using the same active strategy; only
      sessions whose worker actually changes get a new assignment
      record, and every prior record is kept, so assignment history
      is preserved in full
    - available_workers() and worker_load() are computed fresh, from
      each session's most recent assignment, on every call

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, worker_ids: tuple, strategies: tuple, worker_capacity: int = 3):
        """
        Args:
            worker_ids: The fixed pool of execution worker identifiers
                this service distributes sessions across
            strategies: The configured balancing strategies; exactly
                one must have enabled set
            worker_capacity: The maximum number of sessions a single
                worker may hold at once

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingBalancerError:
                If worker_ids is not a non-empty tuple of unique,
                non-blank strings, strategies is not a non-empty tuple
                of
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingStrategy
                with exactly one enabled, or worker_capacity is not a
                positive integer
        """

        if (
            not isinstance(worker_ids, tuple)
            or not worker_ids
            or any(worker_id is None or not isinstance(worker_id, str) or not worker_id.strip() for worker_id in worker_ids)
            or len(set(worker_ids)) != len(worker_ids)
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingBalancerError(
                "Cannot build a session scheduling balancer service with worker_ids that is not a non-empty "
                "tuple of unique, non-blank strings."
            )

        if not isinstance(strategies, tuple) or not strategies or any(
            not isinstance(strategy, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingStrategy)
            for strategy in strategies
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingBalancerError(
                "Cannot build a session scheduling balancer service with strategies that is not a non-empty "
                "tuple of "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingStrategy."
            )

        enabled_strategies = tuple(strategy for strategy in strategies if strategy.enabled)

        if len(enabled_strategies) != 1:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingBalancerError(
                f"Cannot build a session scheduling balancer service with {len(enabled_strategies)} enabled "
                "strategies; exactly one is required."
            )

        if (
            worker_capacity is None
            or isinstance(worker_capacity, bool)
            or not isinstance(worker_capacity, int)
            or worker_capacity <= 0
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingBalancerError(
                "Cannot build a session scheduling balancer service with a non-positive worker_capacity."
            )

        self._worker_ids = worker_ids
        self._strategies = strategies
        self._active_strategy = enabled_strategies[0]
        self._capacity = worker_capacity
        self._assignments = []
        self._current_worker_by_session = {}
        self._round_robin_cursor = 0
        self._lock = RLock()

    def assign(self, session_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingAssignment:
        """
        Place a session on a worker, using the active strategy's
        algorithm among workers currently under capacity.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingBalancerError:
                If session_id is None or blank, or every worker is
                currently at capacity
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            candidates = self._available_workers_locked()

            if not candidates:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingBalancerError(
                    "Cannot assign a session: every execution worker is currently at capacity."
                )

            chosen, self._round_robin_cursor = self._choose(
                candidates, self._worker_load_locked, self._round_robin_cursor
            )

            record = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingAssignment(
                session_id=session_id,
                worker_id=chosen,
                assigned_at=datetime.now(timezone.utc),
            )

            self._assignments.append(record)
            self._current_worker_by_session[session_id] = chosen

            return record

    def rebalance(self) -> tuple:
        """
        Recompute every currently tracked session's placement from
        scratch, using the active strategy, in the order each session
        was first assigned.

        Returns:
            A
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingAssignment
            for every session whose worker actually changed

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingBalancerError:
                If capacity across all workers is insufficient for
                every currently tracked session
        """

        with self._lock:
            session_order = self._session_order_locked()
            loads = {worker_id: 0 for worker_id in self._worker_ids}
            cursor = 0
            moved = []

            for session_id in session_order:
                candidates = tuple(worker_id for worker_id in self._worker_ids if loads[worker_id] < self._capacity)

                if not candidates:
                    raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingBalancerError(
                        "Cannot rebalance: total worker capacity is insufficient for every tracked session."
                    )

                chosen, cursor = self._choose(candidates, lambda worker_id: loads[worker_id], cursor)
                loads[chosen] += 1

                if chosen != self._current_worker_by_session[session_id]:
                    record = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingAssignment(
                        session_id=session_id,
                        worker_id=chosen,
                        assigned_at=datetime.now(timezone.utc),
                    )

                    self._assignments.append(record)
                    self._current_worker_by_session[session_id] = chosen
                    moved.append(record)

            return tuple(moved)

    def worker_load(self, worker_id: str) -> int:
        """
        Count how many sessions are currently placed on a worker.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingBalancerError:
                If worker_id is None or blank, or it is not part of
                this service's worker pool
        """

        self._validate_worker_id(worker_id)

        with self._lock:
            return self._worker_load_locked(worker_id)

    def available_workers(self) -> tuple:
        """
        List every worker currently under capacity, in pool order.
        """

        with self._lock:
            return self._available_workers_locked()

    def strategy(self) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingStrategy:
        """
        Look up the strategy currently in effect.
        """

        return self._active_strategy

    def _choose(self, candidates: tuple, load_of, cursor: int):
        if self._active_strategy.algorithm == "least_loaded":
            chosen = min(candidates, key=lambda worker_id: (load_of(worker_id), self._worker_ids.index(worker_id)))
            return chosen, cursor

        pool_size = len(self._worker_ids)

        for step in range(pool_size):
            index = (cursor + step) % pool_size
            worker_id = self._worker_ids[index]

            if worker_id in candidates:
                return worker_id, index + 1

        return candidates[0], cursor

    def _available_workers_locked(self) -> tuple:
        return tuple(worker_id for worker_id in self._worker_ids if self._worker_load_locked(worker_id) < self._capacity)

    def _worker_load_locked(self, worker_id: str) -> int:
        return sum(1 for current in self._current_worker_by_session.values() if current == worker_id)

    def _session_order_locked(self) -> tuple:
        seen = set()
        order = []

        for record in self._assignments:
            if record.session_id not in seen:
                seen.add(record.session_id)
                order.append(record.session_id)

        return tuple(order)

    def _validate_worker_id(self, worker_id: str) -> None:
        self._validate_id(worker_id, "worker ID")

        if worker_id not in self._worker_ids:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingBalancerError(
                f"Worker ID {worker_id!r} is not part of this service's worker pool."
            )

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingBalancerError(
                f"Cannot operate with an empty or blank {label}."
            )
