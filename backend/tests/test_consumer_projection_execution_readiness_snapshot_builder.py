import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionLifecycleReason,
    ResearchWorkspaceConsumerProjectionExecutionLifecycleReport,
    ResearchWorkspaceConsumerProjectionExecutionLifecycleState,
    ResearchWorkspaceConsumerProjectionExecutionOutcome,
    ResearchWorkspaceConsumerProjectionExecutionOutcomeReason,
    ResearchWorkspaceConsumerProjectionExecutionReadinessSnapshotBuilder,
    ResearchWorkspaceConsumerProjectionExecutionReadinessSnapshotError,
    ResearchWorkspaceConsumerProjectionExecutionSummary,
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


def _make_lifecycle(
    *,
    projection_name="workspace.bootstrap",
    state=READY_STATE,
    reason=READY_FOR_EXECUTION,
    active=True,
):
    return ResearchWorkspaceConsumerProjectionExecutionLifecycleReport(
        projection_name=projection_name,
        state=state,
        reason=reason,
        active=active,
    )


def _make_summary(
    *,
    projection_name="workspace.bootstrap",
    outcome=READY_OUTCOME,
    reason=EXECUTION_APPROVED,
    title="Ready for Execution",
    description="Projection is approved and may proceed.",
    ready_for_execution=True,
):
    return ResearchWorkspaceConsumerProjectionExecutionSummary(
        projection_name=projection_name,
        outcome=outcome,
        reason=reason,
        title=title,
        description=description,
        ready_for_execution=ready_for_execution,
    )


class TestSnapshotBuilding:
    """A valid, aligned pair builds a snapshot."""

    def test_snapshot_builds_successfully(self):
        lifecycle = _make_lifecycle()
        summary = _make_summary()

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionReadinessSnapshotBuilder()
        )
        snapshot = builder.build(lifecycle, summary)

        assert snapshot.projection_name == "workspace.bootstrap"
        assert snapshot.lifecycle_state == READY_STATE
        assert snapshot.reason == READY_FOR_EXECUTION
        assert snapshot.ready_for_execution is True
        assert snapshot.summary == "Projection is approved and may proceed."


class TestReadyLifecycle:
    """READY lifecycle maps to ready_for_execution=True."""

    def test_ready_lifecycle_maps_ready_for_execution_true(self):
        lifecycle = _make_lifecycle(
            state=READY_STATE, reason=READY_FOR_EXECUTION, active=True
        )
        summary = _make_summary(outcome=READY_OUTCOME)

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionReadinessSnapshotBuilder()
        )
        snapshot = builder.build(lifecycle, summary)

        assert snapshot.lifecycle_state == READY_STATE
        assert snapshot.ready_for_execution is True


class TestWaitingLifecycle:
    """WAITING lifecycle maps to ready_for_execution=False."""

    def test_waiting_lifecycle_maps_ready_for_execution_false(self):
        lifecycle = _make_lifecycle(
            state=WAITING, reason=WAITING_FOR_APPROVAL, active=False
        )
        summary = _make_summary(
            outcome=PENDING_OUTCOME,
            reason=APPROVAL_PENDING,
            title="Approval Required",
            description="Projection is awaiting approval before execution.",
            ready_for_execution=False,
        )

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionReadinessSnapshotBuilder()
        )
        snapshot = builder.build(lifecycle, summary)

        assert snapshot.lifecycle_state == WAITING
        assert snapshot.ready_for_execution is False


class TestBlockedLifecycle:
    """BLOCKED lifecycle maps to ready_for_execution=False."""

    def test_blocked_lifecycle_maps_ready_for_execution_false(self):
        lifecycle = _make_lifecycle(
            state=BLOCKED_STATE, reason=EXECUTION_BLOCKED, active=False
        )
        summary = _make_summary(
            outcome=BLOCKED_OUTCOME,
            reason=EXECUTION_REJECTED,
            title="Execution Blocked",
            description="Projection cannot proceed to execution.",
            ready_for_execution=False,
        )

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionReadinessSnapshotBuilder()
        )
        snapshot = builder.build(lifecycle, summary)

        assert snapshot.lifecycle_state == BLOCKED_STATE
        assert snapshot.ready_for_execution is False


class TestProjectionMismatch:
    """Artifacts describing different projections are rejected."""

    def test_projection_mismatch_raises_error(self):
        lifecycle = _make_lifecycle(projection_name="workspace.bootstrap")
        summary = _make_summary(projection_name="workspace.attention")

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionReadinessSnapshotBuilder()
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionReadinessSnapshotError
        ):
            builder.build(lifecycle, summary)


class TestSummaryCopied:
    """summary is set from the execution summary's description."""

    def test_summary_is_copied_from_description(self):
        lifecycle = _make_lifecycle(
            state=WAITING, reason=WAITING_FOR_APPROVAL, active=False
        )
        summary = _make_summary(
            outcome=PENDING_OUTCOME,
            reason=APPROVAL_PENDING,
            title="Approval Required",
            description="Projection is awaiting approval before execution.",
            ready_for_execution=False,
        )

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionReadinessSnapshotBuilder()
        )
        snapshot = builder.build(lifecycle, summary)

        assert (
            snapshot.summary
            == "Projection is awaiting approval before execution."
        )


class TestDeterminism:
    """Building the same pair twice yields equal snapshots."""

    def test_equivalent_inputs_produce_equivalent_snapshots(self):
        lifecycle = _make_lifecycle()
        summary = _make_summary()

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionReadinessSnapshotBuilder()
        )

        first = builder.build(lifecycle, summary)
        second = builder.build(lifecycle, summary)

        assert first == second


class TestArchitecturalBoundaries:
    """Structural guarantees: no state, no mutation, no side effects."""

    def test_builder_has_no_external_dependencies(self):
        builder = (
            ResearchWorkspaceConsumerProjectionExecutionReadinessSnapshotBuilder()
        )

        assert builder.__dict__ == {}

    def test_builder_does_not_mutate_inputs(self):
        lifecycle = _make_lifecycle()
        summary = _make_summary()

        lifecycle_dict = lifecycle.to_dict()
        summary_dict = summary.to_dict()

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionReadinessSnapshotBuilder()
        )
        builder.build(lifecycle, summary)

        assert lifecycle.to_dict() == lifecycle_dict
        assert summary.to_dict() == summary_dict

    def test_snapshot_carries_no_scheduler_or_persistence_state(self):
        lifecycle = _make_lifecycle()
        summary = _make_summary()

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionReadinessSnapshotBuilder()
        )
        snapshot = builder.build(lifecycle, summary)

        assert set(snapshot.to_dict().keys()) == {
            "projection_name",
            "lifecycle_state",
            "reason",
            "ready_for_execution",
            "summary",
        }
