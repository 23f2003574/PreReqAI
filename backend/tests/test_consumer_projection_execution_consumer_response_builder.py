from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionConsumerResponseBuilder,
    ResearchWorkspaceConsumerProjectionExecutionLifecycleReason,
    ResearchWorkspaceConsumerProjectionExecutionLifecycleState,
    ResearchWorkspaceConsumerProjectionExecutionReadinessSnapshot,
)


READY = ResearchWorkspaceConsumerProjectionExecutionLifecycleState.READY
WAITING = ResearchWorkspaceConsumerProjectionExecutionLifecycleState.WAITING
BLOCKED = ResearchWorkspaceConsumerProjectionExecutionLifecycleState.BLOCKED

READY_FOR_EXECUTION = (
    ResearchWorkspaceConsumerProjectionExecutionLifecycleReason.READY_FOR_EXECUTION
)
WAITING_FOR_APPROVAL = (
    ResearchWorkspaceConsumerProjectionExecutionLifecycleReason.WAITING_FOR_APPROVAL
)
EXECUTION_BLOCKED = (
    ResearchWorkspaceConsumerProjectionExecutionLifecycleReason.EXECUTION_BLOCKED
)


def _make_snapshot(
    *,
    projection_name="workspace.bootstrap",
    lifecycle_state=READY,
    reason=READY_FOR_EXECUTION,
    ready_for_execution=True,
    summary="Projection is approved and may proceed.",
):
    return ResearchWorkspaceConsumerProjectionExecutionReadinessSnapshot(
        projection_name=projection_name,
        lifecycle_state=lifecycle_state,
        reason=reason,
        ready_for_execution=ready_for_execution,
        summary=summary,
    )


class TestReadyLifecycle:
    """READY produces the ready-for-execution response."""

    def test_ready_response(self):
        snapshot = _make_snapshot(
            lifecycle_state=READY,
            reason=READY_FOR_EXECUTION,
            ready_for_execution=True,
        )

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionConsumerResponseBuilder()
        )
        response = builder.build(snapshot)

        assert response.title == "Ready for Execution"
        assert response.message == "Projection is ready to execute."


class TestWaitingLifecycle:
    """WAITING produces the awaiting-approval response."""

    def test_waiting_response(self):
        snapshot = _make_snapshot(
            lifecycle_state=WAITING,
            reason=WAITING_FOR_APPROVAL,
            ready_for_execution=False,
        )

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionConsumerResponseBuilder()
        )
        response = builder.build(snapshot)

        assert response.title == "Awaiting Approval"
        assert (
            response.message
            == "Projection is waiting for approval before execution."
        )


class TestBlockedLifecycle:
    """BLOCKED produces the execution-blocked response."""

    def test_blocked_response(self):
        snapshot = _make_snapshot(
            lifecycle_state=BLOCKED,
            reason=EXECUTION_BLOCKED,
            ready_for_execution=False,
        )

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionConsumerResponseBuilder()
        )
        response = builder.build(snapshot)

        assert response.title == "Execution Blocked"
        assert (
            response.message == "Projection is not eligible for execution."
        )


class TestProjectionPreserved:
    """projection_name is copied from the readiness snapshot."""

    def test_projection_name_is_preserved(self):
        snapshot = _make_snapshot(projection_name="workspace.attention")

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionConsumerResponseBuilder()
        )
        response = builder.build(snapshot)

        assert response.projection_name == "workspace.attention"


class TestLifecycleStatePreserved:
    """lifecycle_state is copied from the readiness snapshot, not recomputed."""

    def test_lifecycle_state_is_preserved(self):
        snapshot = _make_snapshot(
            lifecycle_state=WAITING, reason=WAITING_FOR_APPROVAL
        )

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionConsumerResponseBuilder()
        )
        response = builder.build(snapshot)

        assert response.lifecycle_state == WAITING


class TestReadyFlagPreserved:
    """ready_for_execution is copied from the readiness snapshot, not recomputed."""

    def test_ready_flag_true_is_preserved(self):
        snapshot = _make_snapshot(
            lifecycle_state=READY, ready_for_execution=True
        )

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionConsumerResponseBuilder()
        )
        response = builder.build(snapshot)

        assert response.ready_for_execution is True

    def test_ready_flag_false_is_preserved(self):
        snapshot = _make_snapshot(
            lifecycle_state=BLOCKED,
            reason=EXECUTION_BLOCKED,
            ready_for_execution=False,
        )

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionConsumerResponseBuilder()
        )
        response = builder.build(snapshot)

        assert response.ready_for_execution is False


class TestDeterminism:
    """Building the same snapshot twice yields equal responses."""

    def test_equivalent_snapshot_produces_equivalent_responses(self):
        snapshot = _make_snapshot(
            lifecycle_state=WAITING, reason=WAITING_FOR_APPROVAL
        )

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionConsumerResponseBuilder()
        )

        first = builder.build(snapshot)
        second = builder.build(snapshot)

        assert first == second


class TestArchitecturalBoundaries:
    """Structural guarantees: no state, no mutation, no side effects."""

    def test_builder_has_no_external_dependencies(self):
        builder = (
            ResearchWorkspaceConsumerProjectionExecutionConsumerResponseBuilder()
        )

        assert builder.__dict__ == {}

    def test_builder_does_not_mutate_snapshot(self):
        snapshot = _make_snapshot(
            lifecycle_state=WAITING, reason=WAITING_FOR_APPROVAL
        )
        snapshot_dict_before = snapshot.to_dict()

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionConsumerResponseBuilder()
        )
        builder.build(snapshot)

        assert snapshot.to_dict() == snapshot_dict_before

    def test_response_carries_no_execution_state(self):
        snapshot = _make_snapshot(
            lifecycle_state=READY, reason=READY_FOR_EXECUTION
        )

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionConsumerResponseBuilder()
        )
        response = builder.build(snapshot)

        assert set(response.to_dict().keys()) == {
            "projection_name",
            "lifecycle_state",
            "ready_for_execution",
            "title",
            "message",
        }
