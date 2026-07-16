import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionReadiness,
    ResearchWorkspaceConsumerProjectionReadinessAssessment,
    ResearchWorkspaceConsumerProjectionReadinessAssessmentReport,
    ResearchWorkspaceConsumerProjectionReadinessDecisionSnapshotBuilder,
    ResearchWorkspaceConsumerProjectionReadinessDecisionSnapshotError,
    ResearchWorkspaceConsumerProjectionReadinessImpact,
    ResearchWorkspaceConsumerProjectionReadinessImpactSummary,
    ResearchWorkspaceConsumerProjectionReadinessPriority,
    ResearchWorkspaceConsumerProjectionReadinessReason,
    ResearchWorkspaceConsumerProjectionReadinessReasonCode,
    ResearchWorkspaceConsumerProjectionReadinessRecommendation,
    ResearchWorkspaceConsumerProjectionReadinessResponsePackage,
    ResearchWorkspaceConsumerProjectionReadinessTransition,
    ResearchWorkspaceConsumerProjectionReadinessTransitionReport,
)


READY = ResearchWorkspaceConsumerProjectionReadiness.READY
BLOCKED_READINESS = ResearchWorkspaceConsumerProjectionReadiness.BLOCKED

ALL_REQUIREMENTS_MET = (
    ResearchWorkspaceConsumerProjectionReadinessReason.ALL_REQUIREMENTS_MET
)
REQUIRED_DEPENDENCY_MISSING = (
    ResearchWorkspaceConsumerProjectionReadinessReason.REQUIRED_DEPENDENCY_MISSING
)

UNCHANGED = ResearchWorkspaceConsumerProjectionReadinessTransition.UNCHANGED
BLOCKED_TRANSITION = (
    ResearchWorkspaceConsumerProjectionReadinessTransition.BLOCKED
)
RECOVERED = ResearchWorkspaceConsumerProjectionReadinessTransition.RECOVERED

NONE_IMPACT = ResearchWorkspaceConsumerProjectionReadinessImpact.NONE
NEGATIVE = ResearchWorkspaceConsumerProjectionReadinessImpact.NEGATIVE
POSITIVE = ResearchWorkspaceConsumerProjectionReadinessImpact.POSITIVE

STABLE = ResearchWorkspaceConsumerProjectionReadinessAssessment.STABLE
BLOCKED_ASSESSMENT = (
    ResearchWorkspaceConsumerProjectionReadinessAssessment.BLOCKED
)
ASSESSMENT_RECOVERED = (
    ResearchWorkspaceConsumerProjectionReadinessAssessment.RECOVERED
)

NO_ACTION = (
    ResearchWorkspaceConsumerProjectionReadinessRecommendation.NO_ACTION
)
UNBLOCK_EXECUTION = (
    ResearchWorkspaceConsumerProjectionReadinessRecommendation.UNBLOCK_EXECUTION
)

NONE_PRIORITY = ResearchWorkspaceConsumerProjectionReadinessPriority.NONE
CRITICAL = ResearchWorkspaceConsumerProjectionReadinessPriority.CRITICAL

READY_REASON = ResearchWorkspaceConsumerProjectionReadinessReasonCode.READY
BLOCKED_REASON = (
    ResearchWorkspaceConsumerProjectionReadinessReasonCode.BLOCKED
)
RECOVERED_REASON = (
    ResearchWorkspaceConsumerProjectionReadinessReasonCode.RECOVERED
)


def _make_transition(
    *,
    projection_name="workspace.bootstrap",
    previous_readiness=READY,
    current_readiness=READY,
    transition=UNCHANGED,
    previous_reason=ALL_REQUIREMENTS_MET,
    current_reason=ALL_REQUIREMENTS_MET,
):
    return ResearchWorkspaceConsumerProjectionReadinessTransitionReport(
        projection_name=projection_name,
        previous_readiness=previous_readiness,
        current_readiness=current_readiness,
        transition=transition,
        previous_reason=previous_reason,
        current_reason=current_reason,
    )


def _make_impact(
    *,
    projection_name="workspace.bootstrap",
    transition=UNCHANGED,
    impact=NONE_IMPACT,
    appeared_count=0,
    resolved_count=0,
    persistent_count=0,
):
    return ResearchWorkspaceConsumerProjectionReadinessImpactSummary(
        projection_name=projection_name,
        transition=transition,
        impact=impact,
        appeared_count=appeared_count,
        resolved_count=resolved_count,
        persistent_count=persistent_count,
    )


def _make_assessment(
    *,
    projection_name="workspace.bootstrap",
    transition=UNCHANGED,
    impact=NONE_IMPACT,
    assessment=STABLE,
):
    return ResearchWorkspaceConsumerProjectionReadinessAssessmentReport(
        projection_name=projection_name,
        transition=transition,
        impact=impact,
        assessment=assessment,
    )


def _make_response(
    *,
    projection_name="workspace.bootstrap",
    recommendation=NO_ACTION,
    priority=NONE_PRIORITY,
    reason=READY_REASON,
    summary="Projection is ready.",
    action_required=False,
):
    return ResearchWorkspaceConsumerProjectionReadinessResponsePackage(
        projection_name=projection_name,
        recommendation=recommendation,
        priority=priority,
        reason=reason,
        summary=summary,
        action_required=action_required,
    )


class TestSnapshotBuilding:
    """A valid, aligned decision chain builds a snapshot."""

    def test_snapshot_builds_successfully(self):
        transition = _make_transition(transition=UNCHANGED)
        impact = _make_impact(transition=UNCHANGED, impact=NONE_IMPACT)
        assessment = _make_assessment(
            transition=UNCHANGED, impact=NONE_IMPACT, assessment=STABLE
        )
        response = _make_response()

        builder = (
            ResearchWorkspaceConsumerProjectionReadinessDecisionSnapshotBuilder()
        )
        snapshot = builder.build(transition, impact, assessment, response)

        assert snapshot.projection_name == "workspace.bootstrap"
        assert snapshot.transition == UNCHANGED
        assert snapshot.impact == NONE_IMPACT
        assert snapshot.assessment == STABLE


class TestTransitionPreserved:
    """transition is copied from the transition report, not recomputed."""

    def test_transition_is_preserved(self):
        transition = _make_transition(
            previous_readiness=READY,
            current_readiness=BLOCKED_READINESS,
            transition=BLOCKED_TRANSITION,
            current_reason=REQUIRED_DEPENDENCY_MISSING,
        )
        impact = _make_impact(
            transition=BLOCKED_TRANSITION,
            impact=NEGATIVE,
            appeared_count=1,
        )
        assessment = _make_assessment(
            transition=BLOCKED_TRANSITION,
            impact=NEGATIVE,
            assessment=BLOCKED_ASSESSMENT,
        )
        response = _make_response(
            recommendation=UNBLOCK_EXECUTION,
            priority=CRITICAL,
            reason=BLOCKED_REASON,
            summary="Projection execution is blocked.",
            action_required=True,
        )

        builder = (
            ResearchWorkspaceConsumerProjectionReadinessDecisionSnapshotBuilder()
        )
        snapshot = builder.build(transition, impact, assessment, response)

        assert snapshot.transition == BLOCKED_TRANSITION


class TestImpactPreserved:
    """impact is copied from the impact summary, not recomputed."""

    def test_impact_is_preserved(self):
        transition = _make_transition(
            previous_readiness=READY,
            current_readiness=BLOCKED_READINESS,
            transition=BLOCKED_TRANSITION,
            current_reason=REQUIRED_DEPENDENCY_MISSING,
        )
        impact = _make_impact(
            transition=BLOCKED_TRANSITION,
            impact=NEGATIVE,
            appeared_count=1,
        )
        assessment = _make_assessment(
            transition=BLOCKED_TRANSITION,
            impact=NEGATIVE,
            assessment=BLOCKED_ASSESSMENT,
        )
        response = _make_response(
            recommendation=UNBLOCK_EXECUTION,
            priority=CRITICAL,
            reason=BLOCKED_REASON,
            summary="Projection execution is blocked.",
            action_required=True,
        )

        builder = (
            ResearchWorkspaceConsumerProjectionReadinessDecisionSnapshotBuilder()
        )
        snapshot = builder.build(transition, impact, assessment, response)

        assert snapshot.impact == NEGATIVE


class TestAssessmentPreserved:
    """assessment is copied from the assessment report, not recomputed."""

    def test_assessment_is_preserved(self):
        transition = _make_transition(
            previous_readiness=BLOCKED_READINESS,
            current_readiness=READY,
            transition=RECOVERED,
            previous_reason=REQUIRED_DEPENDENCY_MISSING,
        )
        impact = _make_impact(
            transition=RECOVERED,
            impact=POSITIVE,
            resolved_count=1,
        )
        assessment = _make_assessment(
            transition=RECOVERED,
            impact=POSITIVE,
            assessment=ASSESSMENT_RECOVERED,
        )
        response = _make_response(
            recommendation=NO_ACTION,
            priority=NONE_PRIORITY,
            reason=RECOVERED_REASON,
            summary="Projection readiness recovered.",
            action_required=False,
        )

        builder = (
            ResearchWorkspaceConsumerProjectionReadinessDecisionSnapshotBuilder()
        )
        snapshot = builder.build(transition, impact, assessment, response)

        assert snapshot.assessment == ASSESSMENT_RECOVERED


class TestResponseFieldsPreserved:
    """recommendation/priority/reason/summary/action_required all
    copied from the response package, not recomputed."""

    def test_response_fields_are_preserved(self):
        transition = _make_transition(
            previous_readiness=READY,
            current_readiness=BLOCKED_READINESS,
            transition=BLOCKED_TRANSITION,
            current_reason=REQUIRED_DEPENDENCY_MISSING,
        )
        impact = _make_impact(
            transition=BLOCKED_TRANSITION,
            impact=NEGATIVE,
            appeared_count=1,
        )
        assessment = _make_assessment(
            transition=BLOCKED_TRANSITION,
            impact=NEGATIVE,
            assessment=BLOCKED_ASSESSMENT,
        )
        response = _make_response(
            recommendation=UNBLOCK_EXECUTION,
            priority=CRITICAL,
            reason=BLOCKED_REASON,
            summary="Projection execution is blocked.",
            action_required=True,
        )

        builder = (
            ResearchWorkspaceConsumerProjectionReadinessDecisionSnapshotBuilder()
        )
        snapshot = builder.build(transition, impact, assessment, response)

        assert snapshot.recommendation == UNBLOCK_EXECUTION
        assert snapshot.priority == CRITICAL
        assert snapshot.reason == BLOCKED_REASON
        assert snapshot.summary == "Projection execution is blocked."
        assert snapshot.action_required is True


class TestProjectionMismatch:
    """Artifacts describing different projections are rejected."""

    def test_projection_mismatch_raises_error(self):
        transition = _make_transition(projection_name="workspace.bootstrap")
        impact = _make_impact(projection_name="workspace.attention")
        assessment = _make_assessment(projection_name="workspace.bootstrap")
        response = _make_response(projection_name="workspace.bootstrap")

        builder = (
            ResearchWorkspaceConsumerProjectionReadinessDecisionSnapshotBuilder()
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionReadinessDecisionSnapshotError
        ):
            builder.build(transition, impact, assessment, response)


class TestTransitionMismatch:
    """An impact/assessment describing a different transition is rejected."""

    def test_impact_transition_mismatch_raises_error(self):
        transition = _make_transition(transition=UNCHANGED)
        impact = _make_impact(transition=BLOCKED_TRANSITION)
        assessment = _make_assessment(transition=UNCHANGED)
        response = _make_response()

        builder = (
            ResearchWorkspaceConsumerProjectionReadinessDecisionSnapshotBuilder()
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionReadinessDecisionSnapshotError
        ):
            builder.build(transition, impact, assessment, response)

    def test_assessment_transition_mismatch_raises_error(self):
        transition = _make_transition(transition=UNCHANGED)
        impact = _make_impact(transition=UNCHANGED)
        assessment = _make_assessment(transition=BLOCKED_TRANSITION)
        response = _make_response()

        builder = (
            ResearchWorkspaceConsumerProjectionReadinessDecisionSnapshotBuilder()
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionReadinessDecisionSnapshotError
        ):
            builder.build(transition, impact, assessment, response)

    def test_assessment_impact_mismatch_raises_error(self):
        transition = _make_transition(transition=UNCHANGED)
        impact = _make_impact(transition=UNCHANGED, impact=NONE_IMPACT)
        assessment = _make_assessment(
            transition=UNCHANGED, impact=NEGATIVE
        )
        response = _make_response()

        builder = (
            ResearchWorkspaceConsumerProjectionReadinessDecisionSnapshotBuilder()
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionReadinessDecisionSnapshotError
        ):
            builder.build(transition, impact, assessment, response)


class TestDeterminism:
    """Building the same chain twice yields equal snapshots."""

    def test_equivalent_inputs_produce_equivalent_snapshots(self):
        transition = _make_transition(transition=UNCHANGED)
        impact = _make_impact(transition=UNCHANGED)
        assessment = _make_assessment(transition=UNCHANGED, impact=NONE_IMPACT)
        response = _make_response()

        builder = (
            ResearchWorkspaceConsumerProjectionReadinessDecisionSnapshotBuilder()
        )

        first = builder.build(transition, impact, assessment, response)
        second = builder.build(transition, impact, assessment, response)

        assert first == second


class TestArchitecturalBoundaries:
    """Structural guarantees: no state, no mutation, no side effects."""

    def test_builder_has_no_external_dependencies(self):
        builder = (
            ResearchWorkspaceConsumerProjectionReadinessDecisionSnapshotBuilder()
        )

        assert builder.__dict__ == {}

    def test_builder_does_not_mutate_inputs(self):
        transition = _make_transition(transition=UNCHANGED)
        impact = _make_impact(transition=UNCHANGED)
        assessment = _make_assessment(transition=UNCHANGED, impact=NONE_IMPACT)
        response = _make_response()

        transition_dict = transition.to_dict()
        impact_dict = impact.to_dict()
        assessment_dict = assessment.to_dict()
        response_dict = response.to_dict()

        builder = (
            ResearchWorkspaceConsumerProjectionReadinessDecisionSnapshotBuilder()
        )
        builder.build(transition, impact, assessment, response)

        assert transition.to_dict() == transition_dict
        assert impact.to_dict() == impact_dict
        assert assessment.to_dict() == assessment_dict
        assert response.to_dict() == response_dict

    def test_snapshot_carries_no_workflow_or_persistence_state(self):
        transition = _make_transition(transition=UNCHANGED)
        impact = _make_impact(transition=UNCHANGED)
        assessment = _make_assessment(transition=UNCHANGED, impact=NONE_IMPACT)
        response = _make_response()

        builder = (
            ResearchWorkspaceConsumerProjectionReadinessDecisionSnapshotBuilder()
        )
        snapshot = builder.build(transition, impact, assessment, response)

        assert set(snapshot.to_dict().keys()) == {
            "projection_name",
            "transition",
            "impact",
            "assessment",
            "recommendation",
            "priority",
            "reason",
            "summary",
            "action_required",
        }
