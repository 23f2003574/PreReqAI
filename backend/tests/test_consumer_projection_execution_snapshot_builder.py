import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionAuthorization,
    ResearchWorkspaceConsumerProjectionExecutionAuthorizationReason,
    ResearchWorkspaceConsumerProjectionExecutionAuthorizationReport,
    ResearchWorkspaceConsumerProjectionExecutionDecision,
    ResearchWorkspaceConsumerProjectionExecutionDecisionReason,
    ResearchWorkspaceConsumerProjectionExecutionDecisionReport,
    ResearchWorkspaceConsumerProjectionExecutionEligibility,
    ResearchWorkspaceConsumerProjectionExecutionEligibilityReason,
    ResearchWorkspaceConsumerProjectionExecutionEligibilityReport,
    ResearchWorkspaceConsumerProjectionExecutionGateReason,
    ResearchWorkspaceConsumerProjectionExecutionGateReport,
    ResearchWorkspaceConsumerProjectionExecutionGateStatus,
    ResearchWorkspaceConsumerProjectionExecutionOutcome,
    ResearchWorkspaceConsumerProjectionExecutionOutcomeReason,
    ResearchWorkspaceConsumerProjectionExecutionSnapshotBuilder,
    ResearchWorkspaceConsumerProjectionExecutionSnapshotError,
    ResearchWorkspaceConsumerProjectionExecutionSummary,
    ResearchWorkspaceConsumerProjectionExecutionVerdict,
    ResearchWorkspaceConsumerProjectionExecutionVerdictReason,
    ResearchWorkspaceConsumerProjectionExecutionVerdictReport,
)


ELIGIBLE = ResearchWorkspaceConsumerProjectionExecutionEligibility.ELIGIBLE
READY_ELIGIBILITY_REASON = (
    ResearchWorkspaceConsumerProjectionExecutionEligibilityReason.READY
)

EXECUTE = ResearchWorkspaceConsumerProjectionExecutionDecision.EXECUTE
ELIGIBLE_DECISION_REASON = (
    ResearchWorkspaceConsumerProjectionExecutionDecisionReason.ELIGIBLE
)

OPEN = ResearchWorkspaceConsumerProjectionExecutionGateStatus.OPEN
EXECUTION_ALLOWED = (
    ResearchWorkspaceConsumerProjectionExecutionGateReason.EXECUTION_ALLOWED
)

AUTHORIZED = (
    ResearchWorkspaceConsumerProjectionExecutionAuthorization.AUTHORIZED
)
GATE_OPEN = (
    ResearchWorkspaceConsumerProjectionExecutionAuthorizationReason.GATE_OPEN
)

APPROVED = ResearchWorkspaceConsumerProjectionExecutionVerdict.APPROVED
AUTHORIZED_VERDICT_REASON = (
    ResearchWorkspaceConsumerProjectionExecutionVerdictReason.AUTHORIZED
)

READY_OUTCOME = ResearchWorkspaceConsumerProjectionExecutionOutcome.READY
EXECUTION_APPROVED = (
    ResearchWorkspaceConsumerProjectionExecutionOutcomeReason.EXECUTION_APPROVED
)


def _make_eligibility(
    *,
    projection_name="workspace.bootstrap",
    eligibility=ELIGIBLE,
    reason=READY_ELIGIBILITY_REASON,
    executable=True,
):
    return ResearchWorkspaceConsumerProjectionExecutionEligibilityReport(
        projection_name=projection_name,
        eligibility=eligibility,
        reason=reason,
        executable=executable,
    )


def _make_decision(
    *,
    projection_name="workspace.bootstrap",
    decision=EXECUTE,
    reason=ELIGIBLE_DECISION_REASON,
    executable=True,
):
    return ResearchWorkspaceConsumerProjectionExecutionDecisionReport(
        projection_name=projection_name,
        decision=decision,
        reason=reason,
        executable=executable,
    )


def _make_gate(
    *,
    projection_name="workspace.bootstrap",
    status=OPEN,
    reason=EXECUTION_ALLOWED,
    can_continue=True,
):
    return ResearchWorkspaceConsumerProjectionExecutionGateReport(
        projection_name=projection_name,
        status=status,
        reason=reason,
        can_continue=can_continue,
    )


def _make_authorization(
    *,
    projection_name="workspace.bootstrap",
    authorization=AUTHORIZED,
    reason=GATE_OPEN,
    authorized=True,
):
    return ResearchWorkspaceConsumerProjectionExecutionAuthorizationReport(
        projection_name=projection_name,
        authorization=authorization,
        reason=reason,
        authorized=authorized,
    )


def _make_verdict(
    *,
    projection_name="workspace.bootstrap",
    verdict=APPROVED,
    reason=AUTHORIZED_VERDICT_REASON,
    approved=True,
):
    return ResearchWorkspaceConsumerProjectionExecutionVerdictReport(
        projection_name=projection_name,
        verdict=verdict,
        reason=reason,
        approved=approved,
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
    """A valid, aligned artifact chain builds a snapshot."""

    def test_snapshot_builds_successfully(self):
        eligibility = _make_eligibility()
        decision = _make_decision()
        gate = _make_gate()
        authorization = _make_authorization()
        verdict = _make_verdict()
        summary = _make_summary()

        builder = ResearchWorkspaceConsumerProjectionExecutionSnapshotBuilder()
        snapshot = builder.build(
            eligibility, decision, gate, authorization, verdict, summary
        )

        assert snapshot.projection_name == "workspace.bootstrap"
        assert snapshot.eligibility == ELIGIBLE
        assert snapshot.decision == EXECUTE
        assert snapshot.gate == OPEN
        assert snapshot.authorization == AUTHORIZED
        assert snapshot.verdict == APPROVED
        assert snapshot.outcome == READY_OUTCOME


class TestProjectionMismatch:
    """Artifacts describing different projections are rejected."""

    def test_projection_mismatch_raises_error(self):
        eligibility = _make_eligibility(projection_name="workspace.bootstrap")
        decision = _make_decision(projection_name="workspace.attention")
        gate = _make_gate(projection_name="workspace.bootstrap")
        authorization = _make_authorization(
            projection_name="workspace.bootstrap"
        )
        verdict = _make_verdict(projection_name="workspace.bootstrap")
        summary = _make_summary(projection_name="workspace.bootstrap")

        builder = ResearchWorkspaceConsumerProjectionExecutionSnapshotBuilder()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionSnapshotError
        ):
            builder.build(
                eligibility, decision, gate, authorization, verdict, summary
            )


class TestFieldsPreserved:
    """Every field is copied from its source artifact, not recomputed."""

    def test_eligibility_is_preserved(self):
        eligibility = _make_eligibility(eligibility=ELIGIBLE)
        decision = _make_decision()
        gate = _make_gate()
        authorization = _make_authorization()
        verdict = _make_verdict()
        summary = _make_summary()

        builder = ResearchWorkspaceConsumerProjectionExecutionSnapshotBuilder()
        snapshot = builder.build(
            eligibility, decision, gate, authorization, verdict, summary
        )

        assert snapshot.eligibility == ELIGIBLE

    def test_decision_is_preserved(self):
        eligibility = _make_eligibility()
        decision = _make_decision(decision=EXECUTE)
        gate = _make_gate()
        authorization = _make_authorization()
        verdict = _make_verdict()
        summary = _make_summary()

        builder = ResearchWorkspaceConsumerProjectionExecutionSnapshotBuilder()
        snapshot = builder.build(
            eligibility, decision, gate, authorization, verdict, summary
        )

        assert snapshot.decision == EXECUTE

    def test_gate_is_preserved(self):
        eligibility = _make_eligibility()
        decision = _make_decision()
        gate = _make_gate(status=OPEN)
        authorization = _make_authorization()
        verdict = _make_verdict()
        summary = _make_summary()

        builder = ResearchWorkspaceConsumerProjectionExecutionSnapshotBuilder()
        snapshot = builder.build(
            eligibility, decision, gate, authorization, verdict, summary
        )

        assert snapshot.gate == OPEN

    def test_authorization_is_preserved(self):
        eligibility = _make_eligibility()
        decision = _make_decision()
        gate = _make_gate()
        authorization = _make_authorization(authorization=AUTHORIZED)
        verdict = _make_verdict()
        summary = _make_summary()

        builder = ResearchWorkspaceConsumerProjectionExecutionSnapshotBuilder()
        snapshot = builder.build(
            eligibility, decision, gate, authorization, verdict, summary
        )

        assert snapshot.authorization == AUTHORIZED

    def test_verdict_is_preserved(self):
        eligibility = _make_eligibility()
        decision = _make_decision()
        gate = _make_gate()
        authorization = _make_authorization()
        verdict = _make_verdict(verdict=APPROVED)
        summary = _make_summary()

        builder = ResearchWorkspaceConsumerProjectionExecutionSnapshotBuilder()
        snapshot = builder.build(
            eligibility, decision, gate, authorization, verdict, summary
        )

        assert snapshot.verdict == APPROVED

    def test_outcome_is_preserved(self):
        eligibility = _make_eligibility()
        decision = _make_decision()
        gate = _make_gate()
        authorization = _make_authorization()
        verdict = _make_verdict()
        summary = _make_summary(outcome=READY_OUTCOME)

        builder = ResearchWorkspaceConsumerProjectionExecutionSnapshotBuilder()
        snapshot = builder.build(
            eligibility, decision, gate, authorization, verdict, summary
        )

        assert snapshot.outcome == READY_OUTCOME

    def test_summary_fields_are_preserved(self):
        eligibility = _make_eligibility()
        decision = _make_decision()
        gate = _make_gate()
        authorization = _make_authorization()
        verdict = _make_verdict()
        summary = _make_summary(
            reason=EXECUTION_APPROVED,
            title="Ready for Execution",
            description="Projection is approved and may proceed.",
            ready_for_execution=True,
        )

        builder = ResearchWorkspaceConsumerProjectionExecutionSnapshotBuilder()
        snapshot = builder.build(
            eligibility, decision, gate, authorization, verdict, summary
        )

        assert snapshot.reason == EXECUTION_APPROVED
        assert snapshot.title == "Ready for Execution"
        assert (
            snapshot.description
            == "Projection is approved and may proceed."
        )

    def test_ready_flag_is_preserved(self):
        eligibility = _make_eligibility()
        decision = _make_decision()
        gate = _make_gate()
        authorization = _make_authorization()
        verdict = _make_verdict()
        summary = _make_summary(ready_for_execution=True)

        builder = ResearchWorkspaceConsumerProjectionExecutionSnapshotBuilder()
        snapshot = builder.build(
            eligibility, decision, gate, authorization, verdict, summary
        )

        assert snapshot.ready_for_execution is True


class TestDeterminism:
    """Building the same chain twice yields equal snapshots."""

    def test_equivalent_inputs_produce_equivalent_snapshots(self):
        eligibility = _make_eligibility()
        decision = _make_decision()
        gate = _make_gate()
        authorization = _make_authorization()
        verdict = _make_verdict()
        summary = _make_summary()

        builder = ResearchWorkspaceConsumerProjectionExecutionSnapshotBuilder()

        first = builder.build(
            eligibility, decision, gate, authorization, verdict, summary
        )
        second = builder.build(
            eligibility, decision, gate, authorization, verdict, summary
        )

        assert first == second


class TestArchitecturalBoundaries:
    """Structural guarantees: no state, no mutation, no side effects."""

    def test_builder_has_no_external_dependencies(self):
        builder = ResearchWorkspaceConsumerProjectionExecutionSnapshotBuilder()

        assert builder.__dict__ == {}

    def test_builder_does_not_mutate_inputs(self):
        eligibility = _make_eligibility()
        decision = _make_decision()
        gate = _make_gate()
        authorization = _make_authorization()
        verdict = _make_verdict()
        summary = _make_summary()

        eligibility_dict = eligibility.to_dict()
        decision_dict = decision.to_dict()
        gate_dict = gate.to_dict()
        authorization_dict = authorization.to_dict()
        verdict_dict = verdict.to_dict()
        summary_dict = summary.to_dict()

        builder = ResearchWorkspaceConsumerProjectionExecutionSnapshotBuilder()
        builder.build(
            eligibility, decision, gate, authorization, verdict, summary
        )

        assert eligibility.to_dict() == eligibility_dict
        assert decision.to_dict() == decision_dict
        assert gate.to_dict() == gate_dict
        assert authorization.to_dict() == authorization_dict
        assert verdict.to_dict() == verdict_dict
        assert summary.to_dict() == summary_dict

    def test_snapshot_carries_no_execution_or_scheduler_state(self):
        eligibility = _make_eligibility()
        decision = _make_decision()
        gate = _make_gate()
        authorization = _make_authorization()
        verdict = _make_verdict()
        summary = _make_summary()

        builder = ResearchWorkspaceConsumerProjectionExecutionSnapshotBuilder()
        snapshot = builder.build(
            eligibility, decision, gate, authorization, verdict, summary
        )

        assert set(snapshot.to_dict().keys()) == {
            "projection_name",
            "eligibility",
            "decision",
            "gate",
            "authorization",
            "verdict",
            "outcome",
            "reason",
            "title",
            "description",
            "ready_for_execution",
        }
