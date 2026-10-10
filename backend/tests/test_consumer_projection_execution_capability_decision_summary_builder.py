from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionReason,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionReport,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionSummaryBuilder,
)


ACCEPT = ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision.ACCEPT
REVIEW = ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision.REVIEW
REJECT = ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision.REJECT

STANDARD_CAPABILITY = (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionReason.STANDARD_CAPABILITY
)
RESTRICTED_CAPABILITY = (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionReason.RESTRICTED_CAPABILITY
)
UNSUPPORTED_CAPABILITY = (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionReason.UNSUPPORTED_CAPABILITY
)


def _make_decision(
    *,
    projection_name="workspace.bootstrap",
    decision=ACCEPT,
    reason=STANDARD_CAPABILITY,
    executable=True,
):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionReport(
        projection_name=projection_name,
        decision=decision,
        reason=reason,
        executable=executable,
    )


class TestAcceptDecision:
    """ACCEPT produces the capability-accepted presentation."""

    def test_accept_summary(self):
        decision = _make_decision(
            decision=ACCEPT,
            reason=STANDARD_CAPABILITY,
            executable=True,
        )

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionSummaryBuilder()
        )
        summary = builder.build(decision)

        assert summary.title == "Capability Accepted"
        assert (
            summary.description
            == "Projection satisfies execution capability requirements."
        )


class TestReviewDecision:
    """REVIEW produces the capability-requires-review presentation."""

    def test_review_summary(self):
        decision = _make_decision(
            decision=REVIEW,
            reason=RESTRICTED_CAPABILITY,
            executable=False,
        )

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionSummaryBuilder()
        )
        summary = builder.build(decision)

        assert summary.title == "Capability Requires Review"
        assert (
            summary.description
            == "Projection requires manual review before execution."
        )


class TestRejectDecision:
    """REJECT produces the capability-rejected presentation."""

    def test_reject_summary(self):
        decision = _make_decision(
            decision=REJECT,
            reason=UNSUPPORTED_CAPABILITY,
            executable=False,
        )

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionSummaryBuilder()
        )
        summary = builder.build(decision)

        assert summary.title == "Capability Rejected"
        assert (
            summary.description
            == "Projection does not satisfy execution capability requirements."
        )


class TestDecisionReasonPreserved:
    """decision and reason are copied from the report, not recomputed."""

    def test_decision_and_reason_are_preserved(self):
        decision = _make_decision(
            decision=REVIEW,
            reason=RESTRICTED_CAPABILITY,
            executable=False,
        )

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionSummaryBuilder()
        )
        summary = builder.build(decision)

        assert summary.decision == REVIEW
        assert summary.reason == RESTRICTED_CAPABILITY


class TestProjectionPreserved:
    """projection_name is copied from the decision report."""

    def test_projection_name_is_preserved(self):
        decision = _make_decision(projection_name="workspace.attention")

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionSummaryBuilder()
        )
        summary = builder.build(decision)

        assert summary.projection_name == "workspace.attention"


class TestExecutablePreserved:
    """executable is copied from the decision report, not recomputed."""

    def test_executable_flag_true_is_preserved(self):
        decision = _make_decision(decision=ACCEPT, executable=True)

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionSummaryBuilder()
        )
        summary = builder.build(decision)

        assert summary.executable is True

    def test_executable_flag_false_is_preserved(self):
        decision = _make_decision(decision=REJECT, executable=False)

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionSummaryBuilder()
        )
        summary = builder.build(decision)

        assert summary.executable is False


class TestDeterminism:
    """Building the same decision report twice yields equal summaries."""

    def test_equivalent_decision_produces_equivalent_summaries(self):
        decision = _make_decision(
            decision=REVIEW, reason=RESTRICTED_CAPABILITY
        )

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionSummaryBuilder()
        )

        first = builder.build(decision)
        second = builder.build(decision)

        assert first == second


class TestArchitecturalBoundaries:
    """Structural guarantees: no state, no mutation, no side effects."""

    def test_builder_has_no_external_dependencies(self):
        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionSummaryBuilder()
        )

        assert builder.__dict__ == {}

    def test_builder_does_not_mutate_decision(self):
        decision = _make_decision(
            decision=REVIEW, reason=RESTRICTED_CAPABILITY
        )
        decision_dict_before = decision.to_dict()

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionSummaryBuilder()
        )
        builder.build(decision)

        assert decision.to_dict() == decision_dict_before

    def test_summary_carries_no_approval_or_execution_state(self):
        decision = _make_decision(
            decision=ACCEPT, reason=STANDARD_CAPABILITY
        )

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionSummaryBuilder()
        )
        summary = builder.build(decision)

        assert set(summary.to_dict().keys()) == {
            "projection_name",
            "decision",
            "reason",
            "title",
            "description",
            "executable",
        }
