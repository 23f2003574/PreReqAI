from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionDecision,
    ResearchWorkspaceConsumerProjectionExecutionDecisionReason,
    ResearchWorkspaceConsumerProjectionExecutionDecisionResolver,
    ResearchWorkspaceConsumerProjectionExecutionEligibility,
    ResearchWorkspaceConsumerProjectionExecutionEligibilityReason,
    ResearchWorkspaceConsumerProjectionExecutionEligibilityReport,
)


ELIGIBLE = ResearchWorkspaceConsumerProjectionExecutionEligibility.ELIGIBLE
CONDITIONALLY_ELIGIBLE = (
    ResearchWorkspaceConsumerProjectionExecutionEligibility.CONDITIONALLY_ELIGIBLE
)
INELIGIBLE = (
    ResearchWorkspaceConsumerProjectionExecutionEligibility.INELIGIBLE
)

READY_REASON = (
    ResearchWorkspaceConsumerProjectionExecutionEligibilityReason.READY
)
DEGRADED_READY_REASON = (
    ResearchWorkspaceConsumerProjectionExecutionEligibilityReason.DEGRADED_READY
)
BLOCKED_ELIGIBILITY_REASON = (
    ResearchWorkspaceConsumerProjectionExecutionEligibilityReason.BLOCKED
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
CONDITIONAL_REASON = (
    ResearchWorkspaceConsumerProjectionExecutionDecisionReason.CONDITIONAL
)
BLOCKED_DECISION_REASON = (
    ResearchWorkspaceConsumerProjectionExecutionDecisionReason.BLOCKED
)


def _make_eligibility(
    *,
    projection_name="workspace.bootstrap",
    eligibility=ELIGIBLE,
    reason=READY_REASON,
    executable=True,
):
    return ResearchWorkspaceConsumerProjectionExecutionEligibilityReport(
        projection_name=projection_name,
        eligibility=eligibility,
        reason=reason,
        executable=executable,
    )


class TestEligible:
    """ELIGIBLE eligibility resolves to EXECUTE."""

    def test_eligible_produces_execute(self):
        eligibility = _make_eligibility(
            eligibility=ELIGIBLE,
            reason=READY_REASON,
            executable=True,
        )

        resolver = (
            ResearchWorkspaceConsumerProjectionExecutionDecisionResolver()
        )
        report = resolver.resolve(eligibility)

        assert report.decision == EXECUTE
        assert report.reason == ELIGIBLE_REASON


class TestConditionallyEligible:
    """CONDITIONALLY_ELIGIBLE eligibility resolves to WAIT_FOR_APPROVAL."""

    def test_conditionally_eligible_produces_wait_for_approval(self):
        eligibility = _make_eligibility(
            eligibility=CONDITIONALLY_ELIGIBLE,
            reason=DEGRADED_READY_REASON,
            executable=True,
        )

        resolver = (
            ResearchWorkspaceConsumerProjectionExecutionDecisionResolver()
        )
        report = resolver.resolve(eligibility)

        assert report.decision == WAIT_FOR_APPROVAL
        assert report.reason == CONDITIONAL_REASON


class TestIneligible:
    """INELIGIBLE eligibility resolves to DO_NOT_EXECUTE."""

    def test_ineligible_produces_do_not_execute(self):
        eligibility = _make_eligibility(
            eligibility=INELIGIBLE,
            reason=BLOCKED_ELIGIBILITY_REASON,
            executable=False,
        )

        resolver = (
            ResearchWorkspaceConsumerProjectionExecutionDecisionResolver()
        )
        report = resolver.resolve(eligibility)

        assert report.decision == DO_NOT_EXECUTE
        assert report.reason == BLOCKED_DECISION_REASON


class TestProjectionPreserved:
    """projection_name is copied from the eligibility report."""

    def test_projection_name_is_preserved(self):
        eligibility = _make_eligibility(
            projection_name="workspace.attention"
        )

        resolver = (
            ResearchWorkspaceConsumerProjectionExecutionDecisionResolver()
        )
        report = resolver.resolve(eligibility)

        assert report.projection_name == "workspace.attention"


class TestExecutablePreserved:
    """executable is copied from the eligibility report, not recomputed."""

    def test_executable_true_is_preserved(self):
        eligibility = _make_eligibility(
            eligibility=ELIGIBLE, executable=True
        )

        resolver = (
            ResearchWorkspaceConsumerProjectionExecutionDecisionResolver()
        )
        report = resolver.resolve(eligibility)

        assert report.executable is True

    def test_executable_false_is_preserved(self):
        eligibility = _make_eligibility(
            eligibility=INELIGIBLE, executable=False
        )

        resolver = (
            ResearchWorkspaceConsumerProjectionExecutionDecisionResolver()
        )
        report = resolver.resolve(eligibility)

        assert report.executable is False


class TestDeterminism:
    """Resolving the same eligibility report twice yields equal reports."""

    def test_equivalent_eligibility_produces_equivalent_reports(self):
        eligibility = _make_eligibility(eligibility=CONDITIONALLY_ELIGIBLE)

        resolver = (
            ResearchWorkspaceConsumerProjectionExecutionDecisionResolver()
        )

        first = resolver.resolve(eligibility)
        second = resolver.resolve(eligibility)

        assert first == second


class TestArchitecturalBoundaries:
    """Structural guarantees: no state, no mutation, no side effects."""

    def test_resolver_has_no_external_dependencies(self):
        resolver = (
            ResearchWorkspaceConsumerProjectionExecutionDecisionResolver()
        )

        assert resolver.__dict__ == {}

    def test_resolver_does_not_mutate_eligibility(self):
        eligibility = _make_eligibility(eligibility=CONDITIONALLY_ELIGIBLE)
        eligibility_dict_before = eligibility.to_dict()

        resolver = (
            ResearchWorkspaceConsumerProjectionExecutionDecisionResolver()
        )
        resolver.resolve(eligibility)

        assert eligibility.to_dict() == eligibility_dict_before

    def test_report_carries_no_execution_or_scheduling_state(self):
        eligibility = _make_eligibility(eligibility=ELIGIBLE)

        resolver = (
            ResearchWorkspaceConsumerProjectionExecutionDecisionResolver()
        )
        report = resolver.resolve(eligibility)

        assert set(report.to_dict().keys()) == {
            "projection_name",
            "decision",
            "reason",
            "executable",
        }
