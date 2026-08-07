import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingStrategy as Strategy,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingAssignment as Assignment,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingBalancerError as Error,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionSchedulingBalancerService as BalancerService,
)


def _strategy(strategy_id, algorithm, enabled=True):
    return Strategy(strategy_id=strategy_id, algorithm=algorithm, enabled=enabled)


def _least_loaded_service(worker_ids, capacity=3):
    return BalancerService(
        worker_ids=worker_ids,
        strategies=(_strategy("strategy-1", "least_loaded"),),
        worker_capacity=capacity,
    )


class TestWorkspaceSessionSchedulingBalancerService:
    def test_assign_session(self):
        service = _least_loaded_service(("worker-a", "worker-b"))

        assignment = service.assign("session-1")

        assert isinstance(assignment, Assignment)
        assert assignment.session_id == "session-1"
        assert assignment.worker_id in ("worker-a", "worker-b")
        assert service.worker_load(assignment.worker_id) == 1

    def test_rebalance_workers(self):
        service = _least_loaded_service(("worker-a", "worker-b", "worker-c"), capacity=5)

        for index in range(6):
            service.assign(f"session-{index}")

        loads_before = {worker_id: service.worker_load(worker_id) for worker_id in ("worker-a", "worker-b", "worker-c")}
        assert max(loads_before.values()) - min(loads_before.values()) <= 1

        moved = service.rebalance()

        assert isinstance(moved, tuple)

        loads_after = {worker_id: service.worker_load(worker_id) for worker_id in ("worker-a", "worker-b", "worker-c")}
        assert sum(loads_after.values()) == 6
        assert max(loads_after.values()) - min(loads_after.values()) <= 1

        # least-loaded assignment already kept things balanced, so recomputing
        # from scratch reproduces the same placement: rebalance() is a no-op
        assert moved == ()

    def test_load_calculation(self):
        service = _least_loaded_service(("worker-a", "worker-b"), capacity=5)

        service.assign("session-1")
        service.assign("session-2")
        service.assign("session-3")

        assert service.worker_load("worker-a") + service.worker_load("worker-b") == 3

        with pytest.raises(Error):
            service.worker_load("unknown-worker")

    def test_available_worker_lookup(self):
        service = _least_loaded_service(("worker-a", "worker-b"), capacity=1)

        assert service.available_workers() == ("worker-a", "worker-b")

        service.assign("session-1")
        assert service.available_workers() == ("worker-b",)

        service.assign("session-2")
        assert service.available_workers() == ()

    def test_overloaded_worker_avoidance(self):
        service = _least_loaded_service(("worker-a", "worker-b"), capacity=1)

        first = service.assign("session-1")
        second = service.assign("session-2")

        assert first.worker_id != second.worker_id

        with pytest.raises(Error):
            service.assign("session-3")

    def test_strategy_selection(self):
        service = _least_loaded_service(("worker-a",))

        strategy = service.strategy()

        assert isinstance(strategy, Strategy)
        assert strategy.algorithm == "least_loaded"
        assert strategy.enabled is True

        with pytest.raises(Error):
            BalancerService(worker_ids=("worker-a",), strategies=(_strategy("s1", "least_loaded", enabled=False),))

        with pytest.raises(Error):
            BalancerService(
                worker_ids=("worker-a",),
                strategies=(_strategy("s1", "least_loaded"), _strategy("s2", "round_robin")),
            )

        round_robin_service = BalancerService(
            worker_ids=("worker-a", "worker-b"), strategies=(_strategy("s1", "round_robin"),)
        )
        assert round_robin_service.strategy().algorithm == "round_robin"
