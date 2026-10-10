from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityConsumerResponseBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionReason,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionSnapshot,
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


def _make_snapshot(
    *,
    projection_name="workspace.bootstrap",
    decision=ACCEPT,
    reason=STANDARD_CAPABILITY,
    executable=True,
    title="Capability Accepted",
    description="Projection satisfies execution capability requirements.",
):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionSnapshot(
        projection_name=projection_name,
        decision=decision,
        reason=reason,
        executable=executable,
        title=title,
        description=description,
    )


class TestAcceptDecision:
    """ACCEPT produces the capability-accepted presentation."""

    def test_accept_response(self):
        snapshot = _make_snapshot(decision=ACCEPT, reason=STANDARD_CAPABILITY)

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityConsumerResponseBuilder()
        )
        response = builder.build(snapshot)

        assert response.title == "Capability Accepted"
        assert (
            response.message
            == "Projection satisfies all execution capability requirements."
        )


class TestReviewDecision:
    """REVIEW produces the capability-requires-review presentation."""

    def test_review_response(self):
        snapshot = _make_snapshot(
            decision=REVIEW, reason=RESTRICTED_CAPABILITY, executable=False
        )

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityConsumerResponseBuilder()
        )
        response = builder.build(snapshot)

        assert response.title == "Capability Requires Review"
        assert (
            response.message
            == "Projection requires manual review before execution."
        )


class TestRejectDecision:
    """REJECT produces the capability-rejected presentation."""

    def test_reject_response(self):
        snapshot = _make_snapshot(
            decision=REJECT, reason=UNSUPPORTED_CAPABILITY, executable=False
        )

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityConsumerResponseBuilder()
        )
        response = builder.build(snapshot)

        assert response.title == "Capability Rejected"
        assert response.message == (
            "Projection cannot proceed because execution capability "
            "requirements are not satisfied."
        )


class TestProjectionPreserved:
    """projection_name is copied from the decision snapshot."""

    def test_projection_name_is_preserved(self):
        snapshot = _make_snapshot(projection_name="workspace.attention")

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityConsumerResponseBuilder()
        )
        response = builder.build(snapshot)

        assert response.projection_name == "workspace.attention"


class TestExecutablePreserved:
    """executable is copied from the decision snapshot, not recomputed."""

    def test_executable_flag_true_is_preserved(self):
        snapshot = _make_snapshot(decision=ACCEPT, executable=True)

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityConsumerResponseBuilder()
        )
        response = builder.build(snapshot)

        assert response.executable is True

    def test_executable_flag_false_is_preserved(self):
        snapshot = _make_snapshot(decision=REJECT, executable=False)

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityConsumerResponseBuilder()
        )
        response = builder.build(snapshot)

        assert response.executable is False


class TestDecisionPreserved:
    """decision is copied from the decision snapshot, not recomputed."""

    def test_decision_is_preserved(self):
        snapshot = _make_snapshot(decision=REVIEW, reason=RESTRICTED_CAPABILITY)

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityConsumerResponseBuilder()
        )
        response = builder.build(snapshot)

        assert response.decision == REVIEW


class TestDeterminism:
    """Building the same snapshot twice yields equal responses."""

    def test_equivalent_snapshot_produces_equivalent_responses(self):
        snapshot = _make_snapshot(decision=REVIEW, reason=RESTRICTED_CAPABILITY)

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityConsumerResponseBuilder()
        )

        first = builder.build(snapshot)
        second = builder.build(snapshot)

        assert first == second


class TestArchitecturalBoundaries:
    """Structural guarantees: no state, no mutation, no side effects."""

    def test_builder_has_no_external_dependencies(self):
        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityConsumerResponseBuilder()
        )

        assert builder.__dict__ == {}

    def test_builder_does_not_mutate_snapshot(self):
        snapshot = _make_snapshot(decision=REVIEW, reason=RESTRICTED_CAPABILITY)
        snapshot_dict_before = snapshot.to_dict()

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityConsumerResponseBuilder()
        )
        builder.build(snapshot)

        assert snapshot.to_dict() == snapshot_dict_before

    def test_response_carries_no_scheduler_or_approval_state(self):
        snapshot = _make_snapshot(decision=ACCEPT, reason=STANDARD_CAPABILITY)

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityConsumerResponseBuilder()
        )
        response = builder.build(snapshot)

        assert set(response.to_dict().keys()) == {
            "projection_name",
            "decision",
            "executable",
            "title",
            "message",
        }
