from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionDecision,
    ResearchWorkspaceConsumerProjectionExecutionDecisionReason,
    ResearchWorkspaceConsumerProjectionExecutionDecisionReport,
    ResearchWorkspaceConsumerProjectionExecutionGateReason,
    ResearchWorkspaceConsumerProjectionExecutionGateResolver,
    ResearchWorkspaceConsumerProjectionExecutionGateStatus,
)


EXECUTE = ResearchWorkspaceConsumerProjectionExecutionDecision.EXECUTE
WAIT_FOR_APPROVAL = (
    ResearchWorkspaceConsumerProjectionExecutionDecision.WAIT_FOR_APPROVAL
)
DO_NOT_EXECUTE = (
    ResearchWorkspaceConsumerProjectionExecutionDecision.DO_NOT_EXECUTE
)

ELIGIBLE_REASON = (
    ResearchWorkspaceConsumerProjectionExecutionDecisionReason.ELIGIBLE
)
CONDITIONAL_DECISION_REASON = (
    ResearchWorkspaceConsumerProjectionExecutionDecisionReason.CONDITIONAL
)
BLOCKED_DECISION_REASON = (
    ResearchWorkspaceConsumerProjectionExecutionDecisionReason.BLOCKED
)

OPEN = ResearchWorkspaceConsumerProjectionExecutionGateStatus.OPEN
CONDITIONAL = (
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


def _make_decision(
    *,
    projection_name="workspace.bootstrap",
    decision=EXECUTE,
    reason=ELIGIBLE_REASON,
    executable=True,
):
    return ResearchWorkspaceConsumerProjectionExecutionDecisionReport(
        projection_name=projection_name,
        decision=decision,
        reason=reason,
        executable=executable,
    )


class TestExecuteDecision:
    """EXECUTE resolves to OPEN with can_continue=True."""

    def test_execute_produces_open(self):
        decision = _make_decision(
            decision=EXECUTE, reason=ELIGIBLE_REASON, executable=True
        )

        resolver = ResearchWorkspaceConsumerProjectionExecutionGateResolver()
        report = resolver.resolve(decision)

        assert report.status == OPEN
        assert report.reason == EXECUTION_ALLOWED
        assert report.can_continue is True


class TestWaitForApprovalDecision:
    """WAIT_FOR_APPROVAL resolves to CONDITIONAL with can_continue=False."""

    def test_wait_for_approval_produces_conditional(self):
        decision = _make_decision(
            decision=WAIT_FOR_APPROVAL,
            reason=CONDITIONAL_DECISION_REASON,
            executable=True,
        )

        resolver = ResearchWorkspaceConsumerProjectionExecutionGateResolver()
        report = resolver.resolve(decision)

        assert report.status == CONDITIONAL
        assert report.reason == APPROVAL_REQUIRED
        assert report.can_continue is False


class TestDoNotExecuteDecision:
    """DO_NOT_EXECUTE resolves to CLOSED with can_continue=False."""

    def test_do_not_execute_produces_closed(self):
        decision = _make_decision(
            decision=DO_NOT_EXECUTE,
            reason=BLOCKED_DECISION_REASON,
            executable=False,
        )

        resolver = ResearchWorkspaceConsumerProjectionExecutionGateResolver()
        report = resolver.resolve(decision)

        assert report.status == CLOSED
        assert report.reason == EXECUTION_BLOCKED
        assert report.can_continue is False


class TestProjectionPreserved:
    """projection_name is copied from the execution decision report."""

    def test_projection_name_is_preserved(self):
        decision = _make_decision(projection_name="workspace.attention")

        resolver = ResearchWorkspaceConsumerProjectionExecutionGateResolver()
        report = resolver.resolve(decision)

        assert report.projection_name == "workspace.attention"


class TestDeterminism:
    """Resolving the same decision report twice yields equal reports."""

    def test_equivalent_decision_produces_equivalent_reports(self):
        decision = _make_decision(
            decision=WAIT_FOR_APPROVAL, reason=CONDITIONAL_DECISION_REASON
        )

        resolver = ResearchWorkspaceConsumerProjectionExecutionGateResolver()

        first = resolver.resolve(decision)
        second = resolver.resolve(decision)

        assert first == second


class TestArchitecturalBoundaries:
    """Structural guarantees: no state, no mutation, no side effects."""

    def test_resolver_has_no_external_dependencies(self):
        resolver = ResearchWorkspaceConsumerProjectionExecutionGateResolver()

        assert resolver.__dict__ == {}

    def test_resolver_does_not_mutate_decision(self):
        decision = _make_decision(
            decision=WAIT_FOR_APPROVAL, reason=CONDITIONAL_DECISION_REASON
        )
        decision_dict_before = decision.to_dict()

        resolver = ResearchWorkspaceConsumerProjectionExecutionGateResolver()
        resolver.resolve(decision)

        assert decision.to_dict() == decision_dict_before

    def test_report_carries_no_execution_or_scheduler_state(self):
        decision = _make_decision(decision=EXECUTE, reason=ELIGIBLE_REASON)

        resolver = ResearchWorkspaceConsumerProjectionExecutionGateResolver()
        report = resolver.resolve(decision)

        assert set(report.to_dict().keys()) == {
            "projection_name",
            "status",
            "reason",
            "can_continue",
        }
