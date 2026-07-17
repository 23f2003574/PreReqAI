from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionOutcome,
    ResearchWorkspaceConsumerProjectionExecutionOutcomeReason,
    ResearchWorkspaceConsumerProjectionExecutionVerdict,
    ResearchWorkspaceConsumerProjectionExecutionVerdictReason,
    ResearchWorkspaceConsumerProjectionExecutionVerdictReport,
    ResearchWorkspaceConsumerProjectionVerdictOutcomeResolver,
)


APPROVED = ResearchWorkspaceConsumerProjectionExecutionVerdict.APPROVED
PENDING_VERDICT = (
    ResearchWorkspaceConsumerProjectionExecutionVerdict.PENDING
)
REJECTED = ResearchWorkspaceConsumerProjectionExecutionVerdict.REJECTED

AUTHORIZED_REASON = (
    ResearchWorkspaceConsumerProjectionExecutionVerdictReason.AUTHORIZED
)
APPROVAL_REQUIRED_VERDICT_REASON = (
    ResearchWorkspaceConsumerProjectionExecutionVerdictReason.APPROVAL_REQUIRED
)
AUTHORIZATION_DENIED = (
    ResearchWorkspaceConsumerProjectionExecutionVerdictReason.AUTHORIZATION_DENIED
)

READY = ResearchWorkspaceConsumerProjectionExecutionOutcome.READY
PENDING_OUTCOME = (
    ResearchWorkspaceConsumerProjectionExecutionOutcome.PENDING
)
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


def _make_verdict(
    *,
    projection_name="workspace.bootstrap",
    verdict=APPROVED,
    reason=AUTHORIZED_REASON,
    approved=True,
):
    return ResearchWorkspaceConsumerProjectionExecutionVerdictReport(
        projection_name=projection_name,
        verdict=verdict,
        reason=reason,
        approved=approved,
    )


class TestApprovedVerdict:
    """APPROVED resolves to READY with ready_for_execution=True."""

    def test_approved_produces_ready(self):
        verdict = _make_verdict(
            verdict=APPROVED, reason=AUTHORIZED_REASON, approved=True
        )

        resolver = ResearchWorkspaceConsumerProjectionVerdictOutcomeResolver()
        report = resolver.resolve(verdict)

        assert report.outcome == READY
        assert report.reason == EXECUTION_APPROVED
        assert report.ready_for_execution is True


class TestPendingVerdict:
    """PENDING resolves to PENDING with ready_for_execution=False."""

    def test_pending_produces_pending(self):
        verdict = _make_verdict(
            verdict=PENDING_VERDICT,
            reason=APPROVAL_REQUIRED_VERDICT_REASON,
            approved=False,
        )

        resolver = ResearchWorkspaceConsumerProjectionVerdictOutcomeResolver()
        report = resolver.resolve(verdict)

        assert report.outcome == PENDING_OUTCOME
        assert report.reason == APPROVAL_PENDING
        assert report.ready_for_execution is False


class TestRejectedVerdict:
    """REJECTED resolves to BLOCKED with ready_for_execution=False."""

    def test_rejected_produces_blocked(self):
        verdict = _make_verdict(
            verdict=REJECTED, reason=AUTHORIZATION_DENIED, approved=False
        )

        resolver = ResearchWorkspaceConsumerProjectionVerdictOutcomeResolver()
        report = resolver.resolve(verdict)

        assert report.outcome == BLOCKED
        assert report.reason == EXECUTION_REJECTED
        assert report.ready_for_execution is False


class TestProjectionPreserved:
    """projection_name is copied from the verdict report."""

    def test_projection_name_is_preserved(self):
        verdict = _make_verdict(projection_name="workspace.attention")

        resolver = ResearchWorkspaceConsumerProjectionVerdictOutcomeResolver()
        report = resolver.resolve(verdict)

        assert report.projection_name == "workspace.attention"


class TestDeterminism:
    """Resolving the same verdict report twice yields equal reports."""

    def test_equivalent_verdict_produces_equivalent_reports(self):
        verdict = _make_verdict(
            verdict=PENDING_VERDICT, reason=APPROVAL_REQUIRED_VERDICT_REASON
        )

        resolver = ResearchWorkspaceConsumerProjectionVerdictOutcomeResolver()

        first = resolver.resolve(verdict)
        second = resolver.resolve(verdict)

        assert first == second


class TestArchitecturalBoundaries:
    """Structural guarantees: no state, no mutation, no side effects."""

    def test_resolver_has_no_external_dependencies(self):
        resolver = ResearchWorkspaceConsumerProjectionVerdictOutcomeResolver()

        assert resolver.__dict__ == {}

    def test_resolver_does_not_mutate_verdict(self):
        verdict = _make_verdict(
            verdict=PENDING_VERDICT, reason=APPROVAL_REQUIRED_VERDICT_REASON
        )
        verdict_dict_before = verdict.to_dict()

        resolver = ResearchWorkspaceConsumerProjectionVerdictOutcomeResolver()
        resolver.resolve(verdict)

        assert verdict.to_dict() == verdict_dict_before

    def test_report_carries_no_execution_or_infrastructure_state(self):
        verdict = _make_verdict(verdict=APPROVED, reason=AUTHORIZED_REASON)

        resolver = ResearchWorkspaceConsumerProjectionVerdictOutcomeResolver()
        report = resolver.resolve(verdict)

        assert set(report.to_dict().keys()) == {
            "projection_name",
            "outcome",
            "reason",
            "ready_for_execution",
        }
