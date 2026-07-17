from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionAuthorization,
    ResearchWorkspaceConsumerProjectionExecutionAuthorizationReason,
    ResearchWorkspaceConsumerProjectionExecutionAuthorizationResolver,
    ResearchWorkspaceConsumerProjectionExecutionGateReason,
    ResearchWorkspaceConsumerProjectionExecutionGateReport,
    ResearchWorkspaceConsumerProjectionExecutionGateStatus,
)


OPEN = ResearchWorkspaceConsumerProjectionExecutionGateStatus.OPEN
CONDITIONAL_GATE = (
    ResearchWorkspaceConsumerProjectionExecutionGateStatus.CONDITIONAL
)
CLOSED = ResearchWorkspaceConsumerProjectionExecutionGateStatus.CLOSED

EXECUTION_ALLOWED = (
    ResearchWorkspaceConsumerProjectionExecutionGateReason.EXECUTION_ALLOWED
)
APPROVAL_REQUIRED = (
    ResearchWorkspaceConsumerProjectionExecutionGateReason.APPROVAL_REQUIRED
)
EXECUTION_BLOCKED = (
    ResearchWorkspaceConsumerProjectionExecutionGateReason.EXECUTION_BLOCKED
)

AUTHORIZED = (
    ResearchWorkspaceConsumerProjectionExecutionAuthorization.AUTHORIZED
)
CONDITIONAL_AUTHORIZATION = (
    ResearchWorkspaceConsumerProjectionExecutionAuthorization.CONDITIONAL
)
DENIED = ResearchWorkspaceConsumerProjectionExecutionAuthorization.DENIED

GATE_OPEN = (
    ResearchWorkspaceConsumerProjectionExecutionAuthorizationReason.GATE_OPEN
)
APPROVAL_PENDING = (
    ResearchWorkspaceConsumerProjectionExecutionAuthorizationReason.APPROVAL_PENDING
)
GATE_CLOSED = (
    ResearchWorkspaceConsumerProjectionExecutionAuthorizationReason.GATE_CLOSED
)


def _make_gate(
    *,
    projection_name="workspace.bootstrap",
    status=OPEN,
    reason=EXECUTION_ALLOWED,
    can_continue=True,
):
    return ResearchWorkspaceConsumerProjectionExecutionGateReport(
        projection_name=projection_name,
        status=status,
        reason=reason,
        can_continue=can_continue,
    )


class TestOpenGate:
    """OPEN resolves to AUTHORIZED with authorized=True."""

    def test_open_produces_authorized(self):
        gate = _make_gate(
            status=OPEN, reason=EXECUTION_ALLOWED, can_continue=True
        )

        resolver = (
            ResearchWorkspaceConsumerProjectionExecutionAuthorizationResolver()
        )
        report = resolver.resolve(gate)

        assert report.authorization == AUTHORIZED
        assert report.reason == GATE_OPEN
        assert report.authorized is True


class TestConditionalGate:
    """CONDITIONAL resolves to CONDITIONAL with authorized=False."""

    def test_conditional_produces_conditional(self):
        gate = _make_gate(
            status=CONDITIONAL_GATE,
            reason=APPROVAL_REQUIRED,
            can_continue=False,
        )

        resolver = (
            ResearchWorkspaceConsumerProjectionExecutionAuthorizationResolver()
        )
        report = resolver.resolve(gate)

        assert report.authorization == CONDITIONAL_AUTHORIZATION
        assert report.reason == APPROVAL_PENDING
        assert report.authorized is False


class TestClosedGate:
    """CLOSED resolves to DENIED with authorized=False."""

    def test_closed_produces_denied(self):
        gate = _make_gate(
            status=CLOSED, reason=EXECUTION_BLOCKED, can_continue=False
        )

        resolver = (
            ResearchWorkspaceConsumerProjectionExecutionAuthorizationResolver()
        )
        report = resolver.resolve(gate)

        assert report.authorization == DENIED
        assert report.reason == GATE_CLOSED
        assert report.authorized is False


class TestProjectionPreserved:
    """projection_name is copied from the execution gate report."""

    def test_projection_name_is_preserved(self):
        gate = _make_gate(projection_name="workspace.attention")

        resolver = (
            ResearchWorkspaceConsumerProjectionExecutionAuthorizationResolver()
        )
        report = resolver.resolve(gate)

        assert report.projection_name == "workspace.attention"


class TestDeterminism:
    """Resolving the same gate report twice yields equal reports."""

    def test_equivalent_gate_produces_equivalent_reports(self):
        gate = _make_gate(
            status=CONDITIONAL_GATE, reason=APPROVAL_REQUIRED
        )

        resolver = (
            ResearchWorkspaceConsumerProjectionExecutionAuthorizationResolver()
        )

        first = resolver.resolve(gate)
        second = resolver.resolve(gate)

        assert first == second


class TestArchitecturalBoundaries:
    """Structural guarantees: no state, no mutation, no side effects."""

    def test_resolver_has_no_external_dependencies(self):
        resolver = (
            ResearchWorkspaceConsumerProjectionExecutionAuthorizationResolver()
        )

        assert resolver.__dict__ == {}

    def test_resolver_does_not_mutate_gate(self):
        gate = _make_gate(
            status=CONDITIONAL_GATE, reason=APPROVAL_REQUIRED
        )
        gate_dict_before = gate.to_dict()

        resolver = (
            ResearchWorkspaceConsumerProjectionExecutionAuthorizationResolver()
        )
        resolver.resolve(gate)

        assert gate.to_dict() == gate_dict_before

    def test_report_carries_no_execution_or_scheduler_state(self):
        gate = _make_gate(status=OPEN, reason=EXECUTION_ALLOWED)

        resolver = (
            ResearchWorkspaceConsumerProjectionExecutionAuthorizationResolver()
        )
        report = resolver.resolve(gate)

        assert set(report.to_dict().keys()) == {
            "projection_name",
            "authorization",
            "reason",
            "authorized",
        }
