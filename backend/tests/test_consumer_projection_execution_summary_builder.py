from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionOutcome,
    ResearchWorkspaceConsumerProjectionExecutionOutcomeReason,
    ResearchWorkspaceConsumerProjectionExecutionOutcomeReport,
    ResearchWorkspaceConsumerProjectionExecutionSummaryBuilder,
)


READY = ResearchWorkspaceConsumerProjectionExecutionOutcome.READY
PENDING = ResearchWorkspaceConsumerProjectionExecutionOutcome.PENDING
BLOCKED = ResearchWorkspaceConsumerProjectionExecutionOutcome.BLOCKED

EXECUTION_APPROVED = (
    ResearchWorkspaceConsumerProjectionExecutionOutcomeReason.EXECUTION_APPROVED
)
APPROVAL_PENDING = (
    ResearchWorkspaceConsumerProjectionExecutionOutcomeReason.APPROVAL_PENDING
)
EXECUTION_REJECTED = (
    ResearchWorkspaceConsumerProjectionExecutionOutcomeReason.EXECUTION_REJECTED
)


def _make_outcome(
    *,
    projection_name="workspace.bootstrap",
    outcome=READY,
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
    """READY produces the ready-for-execution presentation."""

    def test_ready_summary(self):
        outcome = _make_outcome(
            outcome=READY,
            reason=EXECUTION_APPROVED,
            ready_for_execution=True,
        )

        builder = ResearchWorkspaceConsumerProjectionExecutionSummaryBuilder()
        summary = builder.build(outcome)

        assert summary.title == "Ready for Execution"
        assert (
            summary.description
            == "Projection is approved and may proceed."
        )


class TestPendingOutcome:
    """PENDING produces the approval-required presentation."""

    def test_pending_summary(self):
        outcome = _make_outcome(
            outcome=PENDING,
            reason=APPROVAL_PENDING,
            ready_for_execution=False,
        )

        builder = ResearchWorkspaceConsumerProjectionExecutionSummaryBuilder()
        summary = builder.build(outcome)

        assert summary.title == "Approval Required"
        assert (
            summary.description
            == "Projection is awaiting approval before execution."
        )


class TestBlockedOutcome:
    """BLOCKED produces the execution-blocked presentation."""

    def test_blocked_summary(self):
        outcome = _make_outcome(
            outcome=BLOCKED,
            reason=EXECUTION_REJECTED,
            ready_for_execution=False,
        )

        builder = ResearchWorkspaceConsumerProjectionExecutionSummaryBuilder()
        summary = builder.build(outcome)

        assert summary.title == "Execution Blocked"
        assert (
            summary.description
            == "Projection cannot proceed to execution."
        )


class TestOutcomeReasonPreserved:
    """outcome and reason are copied from the outcome report, not recomputed."""

    def test_outcome_and_reason_are_preserved(self):
        outcome = _make_outcome(
            outcome=PENDING,
            reason=APPROVAL_PENDING,
            ready_for_execution=False,
        )

        builder = ResearchWorkspaceConsumerProjectionExecutionSummaryBuilder()
        summary = builder.build(outcome)

        assert summary.outcome == PENDING
        assert summary.reason == APPROVAL_PENDING


class TestProjectionPreserved:
    """projection_name is copied from the outcome report."""

    def test_projection_name_is_preserved(self):
        outcome = _make_outcome(projection_name="workspace.attention")

        builder = ResearchWorkspaceConsumerProjectionExecutionSummaryBuilder()
        summary = builder.build(outcome)

        assert summary.projection_name == "workspace.attention"


class TestReadyFlagPreserved:
    """ready_for_execution is copied from the outcome report, not recomputed."""

    def test_ready_flag_true_is_preserved(self):
        outcome = _make_outcome(outcome=READY, ready_for_execution=True)

        builder = ResearchWorkspaceConsumerProjectionExecutionSummaryBuilder()
        summary = builder.build(outcome)

        assert summary.ready_for_execution is True

    def test_ready_flag_false_is_preserved(self):
        outcome = _make_outcome(outcome=BLOCKED, ready_for_execution=False)

        builder = ResearchWorkspaceConsumerProjectionExecutionSummaryBuilder()
        summary = builder.build(outcome)

        assert summary.ready_for_execution is False


class TestDeterminism:
    """Building the same outcome report twice yields equal summaries."""

    def test_equivalent_outcome_produces_equivalent_summaries(self):
        outcome = _make_outcome(outcome=PENDING, reason=APPROVAL_PENDING)

        builder = ResearchWorkspaceConsumerProjectionExecutionSummaryBuilder()

        first = builder.build(outcome)
        second = builder.build(outcome)

        assert first == second


class TestArchitecturalBoundaries:
    """Structural guarantees: no state, no mutation, no side effects."""

    def test_builder_has_no_external_dependencies(self):
        builder = ResearchWorkspaceConsumerProjectionExecutionSummaryBuilder()

        assert builder.__dict__ == {}

    def test_builder_does_not_mutate_outcome(self):
        outcome = _make_outcome(outcome=PENDING, reason=APPROVAL_PENDING)
        outcome_dict_before = outcome.to_dict()

        builder = ResearchWorkspaceConsumerProjectionExecutionSummaryBuilder()
        builder.build(outcome)

        assert outcome.to_dict() == outcome_dict_before

    def test_summary_carries_no_execution_state(self):
        outcome = _make_outcome(outcome=READY, reason=EXECUTION_APPROVED)

        builder = ResearchWorkspaceConsumerProjectionExecutionSummaryBuilder()
        summary = builder.build(outcome)

        assert set(summary.to_dict().keys()) == {
            "projection_name",
            "outcome",
            "reason",
            "title",
            "description",
            "ready_for_execution",
        }
