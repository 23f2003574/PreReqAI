from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.session import (
    ExecutionPolicy,
    ExecutionPolicyAssignmentService,
    ExecutionPolicyConflictService,
    ExecutionPolicyEnforcementService,
    ExecutionPolicyEvaluationService,
    ExecutionPolicyExceptionService,
    ExecutionPolicyPrecedenceService,
    ExecutionPolicyService,
    ExecutionPolicySimulation,
    ExecutionPolicySimulationError as Error,
    ExecutionPolicySimulationService,
)


class _FakeSessionService:
    def __init__(self, actions_by_session):
        self._actions_by_session = actions_by_session

    def requested_actions(self, session_id):
        return self._actions_by_session.get(session_id, [])


def _build(actions_by_session=None):
    policy_service = ExecutionPolicyService()
    session_service = _FakeSessionService(actions_by_session or {})
    evaluation_service = ExecutionPolicyEvaluationService(policy_service, session_service)
    assignment_service = ExecutionPolicyAssignmentService(policy_service)
    precedence_service = ExecutionPolicyPrecedenceService(assignment_service)
    conflict_service = ExecutionPolicyConflictService(policy_service)
    exception_service = ExecutionPolicyExceptionService(policy_service)
    enforcement_service = ExecutionPolicyEnforcementService(
        assignment_service,
        evaluation_service,
        conflict_service,
        exception_service,
    )
    simulation_service = ExecutionPolicySimulationService(
        precedence_service,
        evaluation_service,
        exception_service,
        enforcement_service,
    )
    return {
        "policy": policy_service,
        "evaluation": evaluation_service,
        "assignment": assignment_service,
        "precedence": precedence_service,
        "exception": exception_service,
        "enforcement": enforcement_service,
        "simulation": simulation_service,
    }


def _register(policy_service, policy_id, rules=("read",)):
    return policy_service.register(
        ExecutionPolicy(
            policy_id=policy_id,
            name=policy_id,
            rules=frozenset(rules),
        )
    )


class TestExecutionPolicySimulationService:
    def test_allowed_simulation(self):
        services = _build(actions_by_session={"session-1": ["read"]})
        _register(services["policy"], "policy-1", rules=("read",))
        services["assignment"].assign("policy-1", "session", "session-1")

        simulation = services["simulation"].simulate("session-1")

        assert isinstance(simulation, ExecutionPolicySimulation)
        assert simulation.allowed is True
        assert simulation.violations == ()
        assert simulation.policies == ("policy-1",)

    def test_violation_simulation(self):
        services = _build(actions_by_session={"session-1": ["read", "delete"]})
        _register(services["policy"], "policy-1", rules=("read",))
        services["assignment"].assign("policy-1", "session", "session-1")

        simulation = services["simulation"].simulate("session-1")

        assert simulation.allowed is False
        assert simulation.violations == ("policy-1:unpermitted_action:delete",)

    def test_exception_handling(self):
        services = _build(actions_by_session={"session-1": ["read", "delete"]})
        _register(services["policy"], "policy-1", rules=("read",))
        services["assignment"].assign("policy-1", "session", "session-1")

        services["exception"].create(
            "policy-1",
            "session-1",
            "delete",
            "approved",
            datetime.now(timezone.utc) + timedelta(hours=1),
        )

        simulation = services["simulation"].simulate("session-1")

        assert simulation.allowed is True
        assert simulation.violations == ()

    def test_decision_comparison(self):
        services = _build(actions_by_session={"session-1": ["read", "delete"]})
        _register(services["policy"], "policy-1", rules=("read",))
        services["assignment"].assign("policy-1", "session", "session-1")

        simulation = services["simulation"].simulate("session-1")
        decision = services["enforcement"].authorize("session-1")

        assert services["simulation"].compare(simulation.simulation_id, decision.decision_id) is True

    def test_decision_comparison_detects_mismatch(self):
        services = _build(actions_by_session={"session-1": ["read", "delete"]})
        _register(services["policy"], "policy-1", rules=("read",))
        services["assignment"].assign("policy-1", "session", "session-1")

        simulation = services["simulation"].simulate("session-1")
        decision = services["enforcement"].deny("session-1")

        assert services["simulation"].compare(simulation.simulation_id, decision.decision_id) is False

    def test_compare_unknown_simulation_is_an_error(self):
        services = _build()

        with pytest.raises(Error):
            services["simulation"].compare("unknown-simulation", "unknown-decision")

    def test_result_lookup(self):
        services = _build(actions_by_session={"session-1": ["read"]})
        _register(services["policy"], "policy-1", rules=("read",))
        services["assignment"].assign("policy-1", "session", "session-1")

        simulation = services["simulation"].simulate("session-1")

        assert services["simulation"].result(simulation.simulation_id) == simulation

    def test_result_unknown_simulation_is_an_error(self):
        services = _build()

        with pytest.raises(Error):
            services["simulation"].result("unknown-simulation")

    def test_read_only_guarantee(self):
        services = _build(actions_by_session={"session-1": ["read", "delete"]})
        _register(services["policy"], "policy-1", rules=("read",))
        services["assignment"].assign("policy-1", "session", "session-1")

        services["simulation"].simulate("session-1")
        services["simulation"].simulate("session-1")

        assert services["evaluation"].history("session-1") == []
        assert services["enforcement"].history("session-1") == []

    def test_deterministic_result(self):
        services = _build(actions_by_session={"session-1": ["read", "delete", "admin"]})
        _register(services["policy"], "policy-1", rules=("read",))
        services["assignment"].assign("policy-1", "session", "session-1")

        first = services["simulation"].simulate("session-1")
        second = services["simulation"].simulate("session-1")

        assert first.policies == second.policies
        assert first.allowed == second.allowed
        assert first.violations == second.violations
