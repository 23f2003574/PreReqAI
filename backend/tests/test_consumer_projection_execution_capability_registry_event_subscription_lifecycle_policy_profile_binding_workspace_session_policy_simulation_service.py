import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionPolicy as Policy,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionPolicyService as PolicyService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicySimulation as Simulation,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicySimulationError as Error,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicySimulationResult as Result,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicySimulationService as SimulationService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyVersionService as VersionService,
)


def _evaluator(configuration, session_id):
    return configuration.get("max_runtime", 0) >= 3600


def _build(policy_id="policy-1", sessions=("session-1", "session-2")):
    policy_service = PolicyService()
    policy_service.register(
        Policy(policy_id=policy_id, name="standard", max_runtime=3600, max_idle=300, allow_restore=True, enabled=True)
    )

    for session_id in sessions:
        policy_service.assign(session_id, policy_id)

    version_service = VersionService(policy_service, lambda pid: {"max_runtime": 3600})
    simulation_service = SimulationService(
        policy_service,
        version_service,
        sessions_provider=lambda: list(sessions),
        evaluator=_evaluator,
    )

    return policy_service, version_service, simulation_service


class TestWorkspaceSessionPolicySimulationService:
    def test_simulate_policy(self):
        _policy_service, version_service, simulation_service = _build()
        version_service.publish("policy-1")

        simulation = simulation_service.simulate("policy-1")

        assert isinstance(simulation, Simulation)
        assert simulation.policy_id == "policy-1"
        assert simulation.target_version == 1
        assert set(simulation.session_ids) == {"session-1", "session-2"}

        result = simulation_service.report(simulation.simulation_id)
        assert isinstance(result, Result)
        assert set(result.affected) == {"session-1", "session-2"}
        assert set(result.passed) == {"session-1", "session-2"}
        assert result.failed == ()

    def test_compare_versions(self):
        policy_service = PolicyService()
        policy_service.register(
            Policy(policy_id="policy-1", name="standard", max_runtime=3600, max_idle=300, allow_restore=True, enabled=True)
        )
        policy_service.assign("session-1", "policy-1")

        configs = iter([{"max_runtime": 3600, "max_idle": 300}, {"max_runtime": 1800, "max_idle": 300}])
        version_service = VersionService(policy_service, lambda pid: next(configs))
        simulation_service = SimulationService(
            policy_service, version_service, sessions_provider=lambda: ["session-1"], evaluator=_evaluator
        )

        version_one = version_service.publish("policy-1")
        version_two = version_service.publish("policy-1")

        differences = simulation_service.compare(version_one, version_two)
        assert differences == ("max_runtime",)

        with pytest.raises(Error):
            simulation_service.compare(version_one, "not-a-version")

    def test_simulation_report(self):
        _policy_service, version_service, simulation_service = _build()
        version_service.publish("policy-1")
        simulation = simulation_service.simulate("policy-1")

        report = simulation_service.report(simulation.simulation_id)
        assert report == simulation_service.report(simulation.simulation_id)

        with pytest.raises(Error):
            simulation_service.report("never-simulated")

    def test_discard_simulation(self):
        _policy_service, version_service, simulation_service = _build()
        version_service.publish("policy-1")
        simulation = simulation_service.simulate("policy-1")

        simulation_service.discard(simulation.simulation_id)

        with pytest.raises(Error):
            simulation_service.report(simulation.simulation_id)

        with pytest.raises(Error):
            simulation_service.discard(simulation.simulation_id)

    def test_unaffected_sessions(self):
        _policy_service, version_service, simulation_service = _build(sessions=("session-1", "session-2"))
        version_service.publish("policy-1")

        simulation = simulation_service.simulate_sessions(["session-1"])

        assert simulation.session_ids == ("session-1",)

        result = simulation_service.report(simulation.simulation_id)
        assert result.affected == ("session-1",)
        assert "session-2" not in result.affected

    def test_invalid_policy_rejection(self):
        _policy_service, _version_service, simulation_service = _build()

        with pytest.raises(Error):
            simulation_service.simulate("never-published-policy")

        with pytest.raises(Error):
            simulation_service.simulate("   ")

        with pytest.raises(Error):
            simulation_service.simulate_sessions([])
