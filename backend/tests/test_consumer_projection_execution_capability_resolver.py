from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapability,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityReason,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityResolver,
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

CAPABLE = ResearchWorkspaceConsumerProjectionExecutionCapability.CAPABLE
LIMITED = ResearchWorkspaceConsumerProjectionExecutionCapability.LIMITED
INCAPABLE = ResearchWorkspaceConsumerProjectionExecutionCapability.INCAPABLE

READY_REASON = (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityReason.READY
)
APPROVAL_REQUIRED = (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityReason.APPROVAL_REQUIRED
)
EXECUTION_BLOCKED = (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityReason.EXECUTION_BLOCKED
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
    """READY resolves to CAPABLE with executable=True."""

    def test_ready_produces_capable(self):
        outcome = _make_outcome(
            outcome=READY_OUTCOME,
            reason=EXECUTION_APPROVED,
            ready_for_execution=True,
        )

        resolver = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityResolver()
        )
        report = resolver.resolve(outcome)

        assert report.capability == CAPABLE
        assert report.reason == READY_REASON
        assert report.executable is True


class TestPendingOutcome:
    """PENDING resolves to LIMITED with executable=False."""

    def test_pending_produces_limited(self):
        outcome = _make_outcome(
            outcome=PENDING_OUTCOME,
            reason=APPROVAL_PENDING,
            ready_for_execution=False,
        )

        resolver = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityResolver()
        )
        report = resolver.resolve(outcome)

        assert report.capability == LIMITED
        assert report.reason == APPROVAL_REQUIRED
        assert report.executable is False


class TestBlockedOutcome:
    """BLOCKED resolves to INCAPABLE with executable=False."""

    def test_blocked_produces_incapable(self):
        outcome = _make_outcome(
            outcome=BLOCKED_OUTCOME,
            reason=EXECUTION_REJECTED,
            ready_for_execution=False,
        )

        resolver = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityResolver()
        )
        report = resolver.resolve(outcome)

        assert report.capability == INCAPABLE
        assert report.reason == EXECUTION_BLOCKED
        assert report.executable is False


class TestProjectionPreserved:
    """projection_name is copied from the execution outcome report."""

    def test_projection_name_is_preserved(self):
        outcome = _make_outcome(projection_name="workspace.attention")

        resolver = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityResolver()
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
            ResearchWorkspaceConsumerProjectionExecutionCapabilityResolver()
        )

        first = resolver.resolve(outcome)
        second = resolver.resolve(outcome)

        assert first == second


class TestArchitecturalBoundaries:
    """Structural guarantees: no state, no mutation, no side effects."""

    def test_resolver_has_no_external_dependencies(self):
        resolver = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityResolver()
        )

        assert resolver.__dict__ == {}

    def test_resolver_does_not_mutate_outcome(self):
        outcome = _make_outcome(
            outcome=PENDING_OUTCOME, reason=APPROVAL_PENDING
        )
        outcome_dict_before = outcome.to_dict()

        resolver = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityResolver()
        )
        resolver.resolve(outcome)

        assert outcome.to_dict() == outcome_dict_before

    def test_report_carries_no_scheduler_or_executor_state(self):
        outcome = _make_outcome(
            outcome=READY_OUTCOME, reason=EXECUTION_APPROVED
        )

        resolver = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityResolver()
        )
        report = resolver.resolve(outcome)

        assert set(report.to_dict().keys()) == {
            "projection_name",
            "capability",
            "reason",
            "executable",
        }
