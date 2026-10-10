import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionReason,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionReport,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionSnapshotBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionSnapshotError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionSummary,
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


def _make_summary(
    *,
    projection_name="workspace.bootstrap",
    decision=ACCEPT,
    reason=STANDARD_CAPABILITY,
    title="Capability Accepted",
    description="Projection satisfies execution capability requirements.",
    executable=True,
):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionSummary(
        projection_name=projection_name,
        decision=decision,
        reason=reason,
        title=title,
        description=description,
        executable=executable,
    )


class TestSnapshotBuilding:
    """A valid, aligned pair builds a snapshot."""

    def test_snapshot_builds_successfully(self):
        decision = _make_decision()
        summary = _make_summary()

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionSnapshotBuilder()
        )
        snapshot = builder.build(decision, summary)

        assert snapshot.projection_name == "workspace.bootstrap"
        assert snapshot.decision == ACCEPT
        assert snapshot.reason == STANDARD_CAPABILITY
        assert snapshot.executable is True
        assert snapshot.title == "Capability Accepted"
        assert (
            snapshot.description
            == "Projection satisfies execution capability requirements."
        )


class TestProjectionMismatch:
    """Artifacts describing different projections are rejected."""

    def test_projection_mismatch_raises_error(self):
        decision = _make_decision(projection_name="workspace.bootstrap")
        summary = _make_summary(projection_name="workspace.attention")

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionSnapshotBuilder()
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionSnapshotError
        ):
            builder.build(decision, summary)


class TestDecisionMismatch:
    """Artifacts disagreeing on the resolved decision are rejected."""

    def test_decision_mismatch_raises_error(self):
        decision = _make_decision(decision=ACCEPT, reason=STANDARD_CAPABILITY)
        summary = _make_summary(
            decision=REVIEW,
            reason=STANDARD_CAPABILITY,
            title="Capability Requires Review",
            description="Projection requires manual review before execution.",
        )

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionSnapshotBuilder()
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionSnapshotError
        ):
            builder.build(decision, summary)


class TestReasonMismatch:
    """Artifacts disagreeing on the resolved reason are rejected."""

    def test_reason_mismatch_raises_error(self):
        decision = _make_decision(decision=REVIEW, reason=RESTRICTED_CAPABILITY)
        summary = _make_summary(
            decision=REVIEW,
            reason=UNSUPPORTED_CAPABILITY,
            title="Capability Requires Review",
            description="Projection requires manual review before execution.",
            executable=False,
        )

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionSnapshotBuilder()
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionSnapshotError
        ):
            builder.build(decision, summary)


class TestExecutablePreserved:
    """executable is copied from the decision report."""

    def test_executable_is_preserved(self):
        decision = _make_decision(
            decision=REJECT,
            reason=UNSUPPORTED_CAPABILITY,
            executable=False,
        )
        summary = _make_summary(
            decision=REJECT,
            reason=UNSUPPORTED_CAPABILITY,
            title="Capability Rejected",
            description="Projection does not satisfy execution capability requirements.",
            executable=False,
        )

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionSnapshotBuilder()
        )
        snapshot = builder.build(decision, summary)

        assert snapshot.executable is False


class TestTitlePreserved:
    """title is copied from the decision summary."""

    def test_title_is_preserved(self):
        decision = _make_decision()
        summary = _make_summary(title="Capability Accepted")

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionSnapshotBuilder()
        )
        snapshot = builder.build(decision, summary)

        assert snapshot.title == "Capability Accepted"


class TestDescriptionPreserved:
    """description is copied from the decision summary."""

    def test_description_is_preserved(self):
        decision = _make_decision()
        summary = _make_summary(
            description="Projection satisfies execution capability requirements."
        )

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionSnapshotBuilder()
        )
        snapshot = builder.build(decision, summary)

        assert (
            snapshot.description
            == "Projection satisfies execution capability requirements."
        )


class TestDeterminism:
    """Building the same pair twice yields equal snapshots."""

    def test_equivalent_inputs_produce_equivalent_snapshots(self):
        decision = _make_decision()
        summary = _make_summary()

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionSnapshotBuilder()
        )

        first = builder.build(decision, summary)
        second = builder.build(decision, summary)

        assert first == second


class TestArchitecturalBoundaries:
    """Structural guarantees: no state, no mutation, no side effects."""

    def test_builder_has_no_external_dependencies(self):
        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionSnapshotBuilder()
        )

        assert builder.__dict__ == {}

    def test_builder_does_not_mutate_inputs(self):
        decision = _make_decision()
        summary = _make_summary()

        decision_dict = decision.to_dict()
        summary_dict = summary.to_dict()

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionSnapshotBuilder()
        )
        builder.build(decision, summary)

        assert decision.to_dict() == decision_dict
        assert summary.to_dict() == summary_dict

    def test_snapshot_carries_no_scheduler_or_approval_state(self):
        decision = _make_decision()
        summary = _make_summary()

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionSnapshotBuilder()
        )
        snapshot = builder.build(decision, summary)

        assert set(snapshot.to_dict().keys()) == {
            "projection_name",
            "decision",
            "reason",
            "executable",
            "title",
            "description",
        }
