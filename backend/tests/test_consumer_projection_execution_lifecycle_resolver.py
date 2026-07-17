from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionLifecycleReason,
    ResearchWorkspaceConsumerProjectionExecutionLifecycleResolver,
    ResearchWorkspaceConsumerProjectionExecutionLifecycleState,
    ResearchWorkspaceConsumerProjectionExecutionOutcome,
    ResearchWorkspaceConsumerProjectionExecutionOutcomeReason,
    ResearchWorkspaceConsumerProjectionExecutionOutcomeReport,
)


READY_OUTCOME = ResearchWorkspaceConsumerProjectionExecutionOutcome.READY
PENDING_OUTCOME = (
    ResearchWorkspaceConsumerProjectionExecutionOutcome.PENDING
)
BLOCKED_OUTCOME = ResearchWorkspaceConsumerProjectionExecutionOutcome.BLOCKED

EXECUTION_APPROVED = (
    ResearchWorkspaceConsumerProjectionExecutionOutcomeReason.EXECUTION_APPROVED
)
APPROVAL_PENDING = (
    ResearchWorkspaceConsumerProjectionExecutionOutcomeReason.APPROVAL_PENDING
)
EXECUTION_REJECTED = (
    ResearchWorkspaceConsumerProjectionExecutionOutcomeReason.EXECUTION_REJECTED
)

READY_STATE = ResearchWorkspaceConsumerProjectionExecutionLifecycleState.READY
WAITING = ResearchWorkspaceConsumerProjectionExecutionLifecycleState.WAITING
BLOCKED_STATE = (
    ResearchWorkspaceConsumerProjectionExecutionLifecycleState.BLOCKED
)

READY_FOR_EXECUTION = (
    ResearchWorkspaceConsumerProjectionExecutionLifecycleReason.READY_FOR_EXECUTION
)
WAITING_FOR_APPROVAL = (
    ResearchWorkspaceConsumerProjectionExecutionLifecycleReason.WAITING_FOR_APPROVAL
)
EXECUTION_BLOCKED = (
    ResearchWorkspaceConsumerProjectionExecutionLifecycleReason.EXECUTION_BLOCKED
)


def _make_outcome(
    *,
    projection_name="workspace.bootstrap",
    outcome=READY_OUTCOME,
    reason=EXECUTION_APPROVED,
    ready_for_execution=True,
):
    return ResearchWorkspaceConsumerProjectionExecutionOutcomeReport(
        projection_name=projection_name,
        outcome=outcome,
        reason=reason,
        ready_for_execution=ready_for_execution,
    )


class TestReadyOutcome:
    """READY resolves to READY with active=True."""

    def test_ready_produces_ready(self):
        outcome = _make_outcome(
            outcome=READY_OUTCOME,
            reason=EXECUTION_APPROVED,
            ready_for_execution=True,
        )

        resolver = (
            ResearchWorkspaceConsumerProjectionExecutionLifecycleResolver()
        )
        report = resolver.resolve(outcome)

        assert report.state == READY_STATE
        assert report.reason == READY_FOR_EXECUTION
        assert report.active is True


class TestPendingOutcome:
    """PENDING resolves to WAITING with active=False."""

    def test_pending_produces_waiting(self):
        outcome = _make_outcome(
            outcome=PENDING_OUTCOME,
            reason=APPROVAL_PENDING,
            ready_for_execution=False,
        )

        resolver = (
            ResearchWorkspaceConsumerProjectionExecutionLifecycleResolver()
        )
        report = resolver.resolve(outcome)

        assert report.state == WAITING
        assert report.reason == WAITING_FOR_APPROVAL
        assert report.active is False


class TestBlockedOutcome:
    """BLOCKED resolves to BLOCKED with active=False."""

    def test_blocked_produces_blocked(self):
        outcome = _make_outcome(
            outcome=BLOCKED_OUTCOME,
            reason=EXECUTION_REJECTED,
            ready_for_execution=False,
        )

        resolver = (
            ResearchWorkspaceConsumerProjectionExecutionLifecycleResolver()
        )
        report = resolver.resolve(outcome)

        assert report.state == BLOCKED_STATE
        assert report.reason == EXECUTION_BLOCKED
        assert report.active is False


class TestProjectionPreserved:
    """projection_name is copied from the execution outcome report."""

    def test_projection_name_is_preserved(self):
        outcome = _make_outcome(projection_name="workspace.attention")

        resolver = (
            ResearchWorkspaceConsumerProjectionExecutionLifecycleResolver()
        )
        report = resolver.resolve(outcome)

        assert report.projection_name == "workspace.attention"


class TestDeterminism:
    """Resolving the same outcome report twice yields equal reports."""

    def test_equivalent_outcome_produces_equivalent_reports(self):
        outcome = _make_outcome(
            outcome=PENDING_OUTCOME, reason=APPROVAL_PENDING
        )

        resolver = (
            ResearchWorkspaceConsumerProjectionExecutionLifecycleResolver()
        )

        first = resolver.resolve(outcome)
        second = resolver.resolve(outcome)

        assert first == second


class TestArchitecturalBoundaries:
    """Structural guarantees: no state, no mutation, no side effects."""

    def test_resolver_has_no_external_dependencies(self):
        resolver = (
            ResearchWorkspaceConsumerProjectionExecutionLifecycleResolver()
        )

        assert resolver.__dict__ == {}

    def test_resolver_does_not_mutate_outcome(self):
        outcome = _make_outcome(
            outcome=PENDING_OUTCOME, reason=APPROVAL_PENDING
        )
        outcome_dict_before = outcome.to_dict()

        resolver = (
            ResearchWorkspaceConsumerProjectionExecutionLifecycleResolver()
        )
        resolver.resolve(outcome)

        assert outcome.to_dict() == outcome_dict_before

    def test_report_carries_no_orchestration_or_scheduler_state(self):
        outcome = _make_outcome(
            outcome=READY_OUTCOME, reason=EXECUTION_APPROVED
        )

        resolver = (
            ResearchWorkspaceConsumerProjectionExecutionLifecycleResolver()
        )
        report = resolver.resolve(outcome)

        assert set(report.to_dict().keys()) == {
            "projection_name",
            "state",
            "reason",
            "active",
        }
