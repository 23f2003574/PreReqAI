import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionAuthorization,
    ResearchWorkspaceConsumerProjectionExecutionConsumerResponse,
    ResearchWorkspaceConsumerProjectionExecutionDecision,
    ResearchWorkspaceConsumerProjectionExecutionDecisionPackageBuilder,
    ResearchWorkspaceConsumerProjectionExecutionDecisionPackageError,
    ResearchWorkspaceConsumerProjectionExecutionEligibility,
    ResearchWorkspaceConsumerProjectionExecutionGateStatus,
    ResearchWorkspaceConsumerProjectionExecutionLifecycleState,
    ResearchWorkspaceConsumerProjectionExecutionOutcome,
    ResearchWorkspaceConsumerProjectionExecutionOutcomeReason,
    ResearchWorkspaceConsumerProjectionExecutionSnapshot,
    ResearchWorkspaceConsumerProjectionExecutionVerdict,
)


ELIGIBLE = ResearchWorkspaceConsumerProjectionExecutionEligibility.ELIGIBLE
EXECUTE = ResearchWorkspaceConsumerProjectionExecutionDecision.EXECUTE
OPEN = ResearchWorkspaceConsumerProjectionExecutionGateStatus.OPEN
AUTHORIZED = (
    ResearchWorkspaceConsumerProjectionExecutionAuthorization.AUTHORIZED
)
APPROVED = ResearchWorkspaceConsumerProjectionExecutionVerdict.APPROVED

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


def _make_snapshot(
    *,
    projection_name="workspace.bootstrap",
    eligibility=ELIGIBLE,
    decision=EXECUTE,
    gate=OPEN,
    authorization=AUTHORIZED,
    verdict=APPROVED,
    outcome=READY_OUTCOME,
    reason=EXECUTION_APPROVED,
    title="Ready for Execution",
    description="Projection is approved and may proceed.",
    ready_for_execution=True,
):
    return ResearchWorkspaceConsumerProjectionExecutionSnapshot(
        projection_name=projection_name,
        eligibility=eligibility,
        decision=decision,
        gate=gate,
        authorization=authorization,
        verdict=verdict,
        outcome=outcome,
        reason=reason,
        title=title,
        description=description,
        ready_for_execution=ready_for_execution,
    )


def _make_response(
    *,
    projection_name="workspace.bootstrap",
    lifecycle_state=READY_STATE,
    ready_for_execution=True,
    title="Ready for Execution",
    message="Projection is ready to execute.",
):
    return ResearchWorkspaceConsumerProjectionExecutionConsumerResponse(
        projection_name=projection_name,
        lifecycle_state=lifecycle_state,
        ready_for_execution=ready_for_execution,
        title=title,
        message=message,
    )


class TestPackageBuilding:
    """A valid, aligned pair builds a package."""

    def test_package_builds_successfully(self):
        snapshot = _make_snapshot()
        response = _make_response()

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionDecisionPackageBuilder()
        )
        package = builder.build(snapshot, response)

        assert package.projection_name == "workspace.bootstrap"
        assert package.lifecycle_state == READY_STATE
        assert package.outcome == READY_OUTCOME
        assert package.ready_for_execution is True
        assert package.title == "Ready for Execution"
        assert package.message == "Projection is ready to execute."


class TestProjectionMismatch:
    """Artifacts describing different projections are rejected."""

    def test_projection_mismatch_raises_error(self):
        snapshot = _make_snapshot(projection_name="workspace.bootstrap")
        response = _make_response(projection_name="workspace.attention")

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionDecisionPackageBuilder()
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionDecisionPackageError
        ):
            builder.build(snapshot, response)


class TestOutcomePreserved:
    """outcome is copied from the snapshot, not recomputed."""

    def test_outcome_is_preserved(self):
        snapshot = _make_snapshot(
            outcome=BLOCKED_OUTCOME,
            reason=EXECUTION_REJECTED,
            title="Execution Blocked",
            description="Projection cannot proceed to execution.",
            ready_for_execution=False,
        )
        response = _make_response(
            lifecycle_state=BLOCKED_STATE,
            ready_for_execution=False,
            title="Execution Blocked",
            message="Projection is not eligible for execution.",
        )

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionDecisionPackageBuilder()
        )
        package = builder.build(snapshot, response)

        assert package.outcome == BLOCKED_OUTCOME


class TestReadyFlagPreserved:
    """ready_for_execution is copied from the snapshot, not recomputed."""

    def test_ready_flag_true_is_preserved(self):
        snapshot = _make_snapshot(ready_for_execution=True)
        response = _make_response(ready_for_execution=True)

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionDecisionPackageBuilder()
        )
        package = builder.build(snapshot, response)

        assert package.ready_for_execution is True

    def test_ready_flag_false_is_preserved(self):
        snapshot = _make_snapshot(
            outcome=PENDING_OUTCOME,
            reason=APPROVAL_PENDING,
            title="Approval Required",
            description="Projection is awaiting approval before execution.",
            ready_for_execution=False,
        )
        response = _make_response(
            lifecycle_state=WAITING,
            ready_for_execution=False,
            title="Awaiting Approval",
            message="Projection is waiting for approval before execution.",
        )

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionDecisionPackageBuilder()
        )
        package = builder.build(snapshot, response)

        assert package.ready_for_execution is False


class TestTitlePreserved:
    """title is copied from the consumer response, not recomputed."""

    def test_title_is_preserved(self):
        snapshot = _make_snapshot()
        response = _make_response(title="Ready for Execution")

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionDecisionPackageBuilder()
        )
        package = builder.build(snapshot, response)

        assert package.title == "Ready for Execution"


class TestMessagePreserved:
    """message is copied from the consumer response, not recomputed."""

    def test_message_is_preserved(self):
        snapshot = _make_snapshot()
        response = _make_response(
            message="Projection is ready to execute."
        )

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionDecisionPackageBuilder()
        )
        package = builder.build(snapshot, response)

        assert package.message == "Projection is ready to execute."


class TestDeterminism:
    """Building the same pair twice yields equal packages."""

    def test_equivalent_inputs_produce_equivalent_packages(self):
        snapshot = _make_snapshot()
        response = _make_response()

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionDecisionPackageBuilder()
        )

        first = builder.build(snapshot, response)
        second = builder.build(snapshot, response)

        assert first == second


class TestArchitecturalBoundaries:
    """Structural guarantees: no state, no mutation, no side effects."""

    def test_builder_has_no_external_dependencies(self):
        builder = (
            ResearchWorkspaceConsumerProjectionExecutionDecisionPackageBuilder()
        )

        assert builder.__dict__ == {}

    def test_builder_does_not_mutate_inputs(self):
        snapshot = _make_snapshot()
        response = _make_response()

        snapshot_dict = snapshot.to_dict()
        response_dict = response.to_dict()

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionDecisionPackageBuilder()
        )
        builder.build(snapshot, response)

        assert snapshot.to_dict() == snapshot_dict
        assert response.to_dict() == response_dict

    def test_package_carries_no_execution_state(self):
        snapshot = _make_snapshot()
        response = _make_response()

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionDecisionPackageBuilder()
        )
        package = builder.build(snapshot, response)

        assert set(package.to_dict().keys()) == {
            "projection_name",
            "lifecycle_state",
            "outcome",
            "ready_for_execution",
            "title",
            "message",
        }
