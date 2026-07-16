import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionReadiness,
    ResearchWorkspaceConsumerProjectionReadinessAssessment,
    ResearchWorkspaceConsumerProjectionReadinessAssessmentError,
    ResearchWorkspaceConsumerProjectionReadinessAssessor,
    ResearchWorkspaceConsumerProjectionReadinessImpact,
    ResearchWorkspaceConsumerProjectionReadinessImpactSummary,
    ResearchWorkspaceConsumerProjectionReadinessReason,
    ResearchWorkspaceConsumerProjectionReadinessTransition,
    ResearchWorkspaceConsumerProjectionReadinessTransitionReport,
)


READY = ResearchWorkspaceConsumerProjectionReadiness.READY
DEGRADED_READY = ResearchWorkspaceConsumerProjectionReadiness.DEGRADED_READY
BLOCKED_READINESS = ResearchWorkspaceConsumerProjectionReadiness.BLOCKED

ALL_REQUIREMENTS_MET = (
    ResearchWorkspaceConsumerProjectionReadinessReason.ALL_REQUIREMENTS_MET
)
REQUIRED_DEPENDENCY_MISSING = (
    ResearchWorkspaceConsumerProjectionReadinessReason.REQUIRED_DEPENDENCY_MISSING
)

UNCHANGED = ResearchWorkspaceConsumerProjectionReadinessTransition.UNCHANGED
IMPROVED = ResearchWorkspaceConsumerProjectionReadinessTransition.IMPROVED
DEGRADED = ResearchWorkspaceConsumerProjectionReadinessTransition.DEGRADED
BLOCKED_TRANSITION = (
    ResearchWorkspaceConsumerProjectionReadinessTransition.BLOCKED
)
RECOVERED = ResearchWorkspaceConsumerProjectionReadinessTransition.RECOVERED

NONE_IMPACT = ResearchWorkspaceConsumerProjectionReadinessImpact.NONE
POSITIVE = ResearchWorkspaceConsumerProjectionReadinessImpact.POSITIVE
NEGATIVE = ResearchWorkspaceConsumerProjectionReadinessImpact.NEGATIVE
MIXED_IMPACT = ResearchWorkspaceConsumerProjectionReadinessImpact.MIXED

STABLE = ResearchWorkspaceConsumerProjectionReadinessAssessment.STABLE
IMPROVING = ResearchWorkspaceConsumerProjectionReadinessAssessment.IMPROVING
ASSESSMENT_RECOVERED = (
    ResearchWorkspaceConsumerProjectionReadinessAssessment.RECOVERED
)
DETERIORATING = (
    ResearchWorkspaceConsumerProjectionReadinessAssessment.DETERIORATING
)
ASSESSMENT_BLOCKED = (
    ResearchWorkspaceConsumerProjectionReadinessAssessment.BLOCKED
)
ASSESSMENT_MIXED = (
    ResearchWorkspaceConsumerProjectionReadinessAssessment.MIXED
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


class TestAssessmentResolution:
    """Test the assessment resolution precedence table."""

    def test_blocked_transition_produces_blocked(self):
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

        assessor = ResearchWorkspaceConsumerProjectionReadinessAssessor()
        assessment = assessor.assess(transition, impact)

        assert assessment.assessment == ASSESSMENT_BLOCKED

    def test_recovered_transition_produces_recovered(self):
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

        assessor = ResearchWorkspaceConsumerProjectionReadinessAssessor()
        assessment = assessor.assess(transition, impact)

        assert assessment.assessment == ASSESSMENT_RECOVERED

    def test_improved_transition_produces_improving(self):
        transition = _make_transition(
            previous_readiness=BLOCKED_READINESS,
            current_readiness=DEGRADED_READY,
            transition=IMPROVED,
            previous_reason=REQUIRED_DEPENDENCY_MISSING,
        )
        impact = _make_impact(
            transition=IMPROVED,
            impact=POSITIVE,
            resolved_count=1,
        )

        assessor = ResearchWorkspaceConsumerProjectionReadinessAssessor()
        assessment = assessor.assess(transition, impact)

        assert assessment.assessment == IMPROVING

    def test_degraded_transition_produces_deteriorating(self):
        transition = _make_transition(
            previous_readiness=READY,
            current_readiness=DEGRADED_READY,
            transition=DEGRADED,
        )
        impact = _make_impact(
            transition=DEGRADED,
            impact=NEGATIVE,
            appeared_count=1,
        )

        assessor = ResearchWorkspaceConsumerProjectionReadinessAssessor()
        assessment = assessor.assess(transition, impact)

        assert assessment.assessment == DETERIORATING

    def test_unchanged_none_produces_stable(self):
        transition = _make_transition(transition=UNCHANGED)
        impact = _make_impact(transition=UNCHANGED, impact=NONE_IMPACT)

        assessor = ResearchWorkspaceConsumerProjectionReadinessAssessor()
        assessment = assessor.assess(transition, impact)

        assert assessment.assessment == STABLE

    def test_unchanged_positive_produces_improving(self):
        transition = _make_transition(transition=UNCHANGED)
        impact = _make_impact(
            transition=UNCHANGED,
            impact=POSITIVE,
            resolved_count=1,
        )

        assessor = ResearchWorkspaceConsumerProjectionReadinessAssessor()
        assessment = assessor.assess(transition, impact)

        assert assessment.assessment == IMPROVING

    def test_unchanged_negative_produces_deteriorating(self):
        transition = _make_transition(transition=UNCHANGED)
        impact = _make_impact(
            transition=UNCHANGED,
            impact=NEGATIVE,
            appeared_count=1,
        )

        assessor = ResearchWorkspaceConsumerProjectionReadinessAssessor()
        assessment = assessor.assess(transition, impact)

        assert assessment.assessment == DETERIORATING

    def test_unchanged_mixed_produces_mixed(self):
        transition = _make_transition(transition=UNCHANGED)
        impact = _make_impact(
            transition=UNCHANGED,
            impact=MIXED_IMPACT,
            appeared_count=1,
            resolved_count=1,
        )

        assessor = ResearchWorkspaceConsumerProjectionReadinessAssessor()
        assessment = assessor.assess(transition, impact)

        assert assessment.assessment == ASSESSMENT_MIXED


class TestRequiresAttention:
    """Test the derived requires_attention property."""

    def test_requires_attention_true_for_blocked(self):
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

        assessor = ResearchWorkspaceConsumerProjectionReadinessAssessor()
        assessment = assessor.assess(transition, impact)

        assert assessment.requires_attention is True

    def test_requires_attention_true_for_deteriorating(self):
        transition = _make_transition(transition=UNCHANGED)
        impact = _make_impact(
            transition=UNCHANGED,
            impact=NEGATIVE,
            appeared_count=1,
        )

        assessor = ResearchWorkspaceConsumerProjectionReadinessAssessor()
        assessment = assessor.assess(transition, impact)

        assert assessment.requires_attention is True

    def test_requires_attention_true_for_mixed(self):
        transition = _make_transition(transition=UNCHANGED)
        impact = _make_impact(
            transition=UNCHANGED,
            impact=MIXED_IMPACT,
            appeared_count=1,
            resolved_count=1,
        )

        assessor = ResearchWorkspaceConsumerProjectionReadinessAssessor()
        assessment = assessor.assess(transition, impact)

        assert assessment.requires_attention is True

    def test_requires_attention_false_for_stable(self):
        transition = _make_transition(transition=UNCHANGED)
        impact = _make_impact(transition=UNCHANGED, impact=NONE_IMPACT)

        assessor = ResearchWorkspaceConsumerProjectionReadinessAssessor()
        assessment = assessor.assess(transition, impact)

        assert assessment.requires_attention is False

    def test_requires_attention_false_for_improving(self):
        transition = _make_transition(
            previous_readiness=BLOCKED_READINESS,
            current_readiness=DEGRADED_READY,
            transition=IMPROVED,
            previous_reason=REQUIRED_DEPENDENCY_MISSING,
        )
        impact = _make_impact(
            transition=IMPROVED,
            impact=POSITIVE,
            resolved_count=1,
        )

        assessor = ResearchWorkspaceConsumerProjectionReadinessAssessor()
        assessment = assessor.assess(transition, impact)

        assert assessment.requires_attention is False

    def test_requires_attention_false_for_recovered(self):
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

        assessor = ResearchWorkspaceConsumerProjectionReadinessAssessor()
        assessment = assessor.assess(transition, impact)

        assert assessment.requires_attention is False


class TestValidation:
    """Test rejection of misaligned artifacts."""

    def test_projection_mismatch_raises_error(self):
        transition = _make_transition(projection_name="workspace.bootstrap")
        impact = _make_impact(projection_name="workspace.attention")

        assessor = ResearchWorkspaceConsumerProjectionReadinessAssessor()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionReadinessAssessmentError
        ):
            assessor.assess(transition, impact)

    def test_transition_mismatch_raises_error(self):
        transition = _make_transition(transition=IMPROVED)
        impact = _make_impact(transition=DEGRADED)

        assessor = ResearchWorkspaceConsumerProjectionReadinessAssessor()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionReadinessAssessmentError
        ):
            assessor.assess(transition, impact)


class TestIdentityPreservation:
    """Test transition and impact fields are reused, not regenerated."""

    def test_identity_fields_are_preserved(self):
        transition = _make_transition(
            projection_name="workspace.attention",
            previous_readiness=READY,
            current_readiness=DEGRADED_READY,
            transition=DEGRADED,
        )
        impact = _make_impact(
            projection_name="workspace.attention",
            transition=DEGRADED,
            impact=NEGATIVE,
            appeared_count=1,
        )

        assessor = ResearchWorkspaceConsumerProjectionReadinessAssessor()
        assessment = assessor.assess(transition, impact)

        assert assessment.projection_name == "workspace.attention"
        assert assessment.transition == DEGRADED
        assert assessment.impact == NEGATIVE


class TestDeterminism:
    """Test assessment resolution is deterministic."""

    def test_equivalent_inputs_produce_equivalent_assessments(self):
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

        assessor = ResearchWorkspaceConsumerProjectionReadinessAssessor()

        assessment1 = assessor.assess(transition, impact)
        assessment2 = assessor.assess(transition, impact)

        assert assessment1 == assessment2


class TestArchitecturalBoundaries:
    """Test structural guarantees of the assessor."""

    def test_assessor_has_no_external_dependencies(self):
        assessor = ResearchWorkspaceConsumerProjectionReadinessAssessor()

        assert assessor.__dict__ == {}

    def test_assessor_does_not_mutate_input_artifacts(self):
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

        transition_dict = transition.to_dict()
        impact_dict = impact.to_dict()

        assessor = ResearchWorkspaceConsumerProjectionReadinessAssessor()
        assessor.assess(transition, impact)

        assert transition.to_dict() == transition_dict
        assert impact.to_dict() == impact_dict

    def test_assessor_works_from_artifacts_alone(self):
        # No readiness report, explanation, or plan object is ever
        # constructed here - proves the assessor only needs the
        # transition and impact summary.
        transition = _make_transition(
            projection_name="artifacts-only",
            previous_readiness=BLOCKED_READINESS,
            current_readiness=READY,
            transition=RECOVERED,
            previous_reason=REQUIRED_DEPENDENCY_MISSING,
        )
        impact = _make_impact(
            projection_name="artifacts-only",
            transition=RECOVERED,
            impact=POSITIVE,
            resolved_count=1,
        )

        assessor = ResearchWorkspaceConsumerProjectionReadinessAssessor()
        assessment = assessor.assess(transition, impact)

        assert assessment.assessment == ASSESSMENT_RECOVERED
