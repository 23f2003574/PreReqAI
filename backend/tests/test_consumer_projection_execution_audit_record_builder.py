import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionAuditRecordBuilder,
    ResearchWorkspaceConsumerProjectionExecutionAuditRecordError,
    ResearchWorkspaceConsumerProjectionExecutionAuthorization,
    ResearchWorkspaceConsumerProjectionExecutionDecision,
    ResearchWorkspaceConsumerProjectionExecutionEligibility,
    ResearchWorkspaceConsumerProjectionExecutionGateStatus,
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


def _make_snapshot(
    *,
    projection_name="workspace.bootstrap",
    eligibility=ELIGIBLE,
    decision=EXECUTE,
    gate=OPEN,
    authorization=AUTHORIZED,
    verdict=APPROVED,
    outcome=READY,
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


class TestRecordBuilding:
    """A valid snapshot builds a record."""

    def test_record_builds_successfully(self):
        snapshot = _make_snapshot()

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionAuditRecordBuilder()
        )
        record = builder.build(snapshot)

        assert record.projection_name == "workspace.bootstrap"
        assert record.outcome == READY
        assert record.verdict == APPROVED
        assert record.authorization == AUTHORIZED
        assert record.ready_for_execution is True
        assert record.summary == "Projection is approved and may proceed."


class TestProjectionPreserved:
    """projection_name is copied from the snapshot."""

    def test_projection_name_is_preserved(self):
        snapshot = _make_snapshot(projection_name="workspace.attention")

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionAuditRecordBuilder()
        )
        record = builder.build(snapshot)

        assert record.projection_name == "workspace.attention"


class TestOutcomePreserved:
    """outcome is copied from the snapshot, not recomputed."""

    def test_outcome_is_preserved(self):
        snapshot = _make_snapshot(
            outcome=BLOCKED,
            reason=EXECUTION_REJECTED,
            title="Execution Blocked",
            description="Projection cannot proceed to execution.",
            ready_for_execution=False,
        )

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionAuditRecordBuilder()
        )
        record = builder.build(snapshot)

        assert record.outcome == BLOCKED


class TestVerdictPreserved:
    """verdict is copied from the snapshot, not recomputed."""

    def test_verdict_is_preserved(self):
        snapshot = _make_snapshot(verdict=APPROVED)

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionAuditRecordBuilder()
        )
        record = builder.build(snapshot)

        assert record.verdict == APPROVED


class TestAuthorizationPreserved:
    """authorization is copied from the snapshot, not recomputed."""

    def test_authorization_is_preserved(self):
        snapshot = _make_snapshot(authorization=AUTHORIZED)

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionAuditRecordBuilder()
        )
        record = builder.build(snapshot)

        assert record.authorization == AUTHORIZED


class TestReadyFlagPreserved:
    """ready_for_execution is copied from the snapshot, not recomputed."""

    def test_ready_flag_true_is_preserved(self):
        snapshot = _make_snapshot(ready_for_execution=True)

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionAuditRecordBuilder()
        )
        record = builder.build(snapshot)

        assert record.ready_for_execution is True

    def test_ready_flag_false_is_preserved(self):
        snapshot = _make_snapshot(
            outcome=PENDING,
            reason=APPROVAL_PENDING,
            title="Approval Required",
            description="Projection is awaiting approval before execution.",
            ready_for_execution=False,
        )

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionAuditRecordBuilder()
        )
        record = builder.build(snapshot)

        assert record.ready_for_execution is False


class TestSummaryCopied:
    """summary is set from the snapshot's description."""

    def test_summary_is_copied_from_description(self):
        snapshot = _make_snapshot(
            outcome=PENDING,
            reason=APPROVAL_PENDING,
            title="Approval Required",
            description="Projection is awaiting approval before execution.",
            ready_for_execution=False,
        )

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionAuditRecordBuilder()
        )
        record = builder.build(snapshot)

        assert (
            record.summary
            == "Projection is awaiting approval before execution."
        )


class TestEmptyProjectionRejected:
    """A snapshot with an empty projection name is rejected."""

    def test_empty_projection_name_raises_error(self):
        snapshot = _make_snapshot(projection_name="")

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionAuditRecordBuilder()
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionAuditRecordError
        ):
            builder.build(snapshot)


class TestDeterminism:
    """Building the same snapshot twice yields equal records."""

    def test_equivalent_snapshot_produces_equivalent_records(self):
        snapshot = _make_snapshot()

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionAuditRecordBuilder()
        )

        first = builder.build(snapshot)
        second = builder.build(snapshot)

        assert first == second


class TestArchitecturalBoundaries:
    """Structural guarantees: no state, no mutation, no side effects."""

    def test_builder_has_no_external_dependencies(self):
        builder = (
            ResearchWorkspaceConsumerProjectionExecutionAuditRecordBuilder()
        )

        assert builder.__dict__ == {}

    def test_builder_does_not_mutate_snapshot(self):
        snapshot = _make_snapshot()
        snapshot_dict_before = snapshot.to_dict()

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionAuditRecordBuilder()
        )
        builder.build(snapshot)

        assert snapshot.to_dict() == snapshot_dict_before

    def test_record_carries_no_logging_or_persistence_state(self):
        snapshot = _make_snapshot()

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionAuditRecordBuilder()
        )
        record = builder.build(snapshot)

        assert set(record.to_dict().keys()) == {
            "projection_name",
            "outcome",
            "verdict",
            "authorization",
            "ready_for_execution",
            "summary",
        }
