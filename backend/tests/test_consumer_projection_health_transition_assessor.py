import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionHealth,
    ResearchWorkspaceConsumerProjectionExecutionHealthTransition,
    ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentError,
    ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind,
    ResearchWorkspaceConsumerProjectionHealthTransitionAssessor,
    ResearchWorkspaceConsumerProjectionHealthTransitionImpact,
    ResearchWorkspaceConsumerProjectionHealthTransitionImpactSummary,
    ResearchWorkspaceConsumerProjectionHealthTransitionKind,
)


def _make_transition(
    *,
    projection_name="workspace.bootstrap",
    previous_execution_id="exec-1",
    current_execution_id="exec-2",
    previous_health=ResearchWorkspaceConsumerProjectionExecutionHealth.HEALTHY,
    current_health=ResearchWorkspaceConsumerProjectionExecutionHealth.HEALTHY,
    kind=ResearchWorkspaceConsumerProjectionHealthTransitionKind.UNCHANGED,
):
    return ResearchWorkspaceConsumerProjectionExecutionHealthTransition(
        projection_name=projection_name,
        previous_execution_id=previous_execution_id,
        current_execution_id=current_execution_id,
        previous_health=previous_health,
        current_health=current_health,
        kind=kind,
    )


def _make_impact_summary(
    *,
    projection_name="workspace.bootstrap",
    previous_execution_id="exec-1",
    current_execution_id="exec-2",
    transition=ResearchWorkspaceConsumerProjectionHealthTransitionKind.UNCHANGED,
    impact=ResearchWorkspaceConsumerProjectionHealthTransitionImpact.NONE,
    appeared_count=0,
    resolved_count=0,
    persistent_count=0,
    severity_increase_count=0,
    severity_decrease_count=0,
):
    return ResearchWorkspaceConsumerProjectionHealthTransitionImpactSummary(
        projection_name=projection_name,
        previous_execution_id=previous_execution_id,
        current_execution_id=current_execution_id,
        transition=transition,
        impact=impact,
        appeared_count=appeared_count,
        resolved_count=resolved_count,
        persistent_count=persistent_count,
        severity_increase_count=severity_increase_count,
        severity_decrease_count=severity_decrease_count,
    )


UNCHANGED = ResearchWorkspaceConsumerProjectionHealthTransitionKind.UNCHANGED
IMPROVED = ResearchWorkspaceConsumerProjectionHealthTransitionKind.IMPROVED
DETERIORATED = ResearchWorkspaceConsumerProjectionHealthTransitionKind.DETERIORATED
RECOVERED = ResearchWorkspaceConsumerProjectionHealthTransitionKind.RECOVERED
BECAME_CRITICAL = ResearchWorkspaceConsumerProjectionHealthTransitionKind.BECAME_CRITICAL

NONE_IMPACT = ResearchWorkspaceConsumerProjectionHealthTransitionImpact.NONE
POSITIVE = ResearchWorkspaceConsumerProjectionHealthTransitionImpact.POSITIVE
NEGATIVE = ResearchWorkspaceConsumerProjectionHealthTransitionImpact.NEGATIVE
MIXED_IMPACT = ResearchWorkspaceConsumerProjectionHealthTransitionImpact.MIXED

STABLE = ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind.STABLE
IMPROVING = ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind.IMPROVING
ASSESSMENT_RECOVERED = ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind.RECOVERED
DETERIORATING = ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind.DETERIORATING
ESCALATED = ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind.ESCALATED
ASSESSMENT_MIXED = ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind.MIXED


class TestAssessmentResolution:
    """Test the assessment resolution precedence table."""

    def test_unchanged_none_produces_stable(self):
        transition = _make_transition(kind=UNCHANGED)
        impact = _make_impact_summary(transition=UNCHANGED, impact=NONE_IMPACT)

        assessor = ResearchWorkspaceConsumerProjectionHealthTransitionAssessor()
        assessment = assessor.assess(transition, impact)

        assert assessment.assessment == STABLE

    def test_unchanged_positive_produces_improving(self):
        transition = _make_transition(kind=UNCHANGED)
        impact = _make_impact_summary(transition=UNCHANGED, impact=POSITIVE)

        assessor = ResearchWorkspaceConsumerProjectionHealthTransitionAssessor()
        assessment = assessor.assess(transition, impact)

        assert assessment.assessment == IMPROVING

    def test_unchanged_negative_produces_deteriorating(self):
        transition = _make_transition(kind=UNCHANGED)
        impact = _make_impact_summary(transition=UNCHANGED, impact=NEGATIVE)

        assessor = ResearchWorkspaceConsumerProjectionHealthTransitionAssessor()
        assessment = assessor.assess(transition, impact)

        assert assessment.assessment == DETERIORATING

    def test_unchanged_mixed_produces_mixed(self):
        transition = _make_transition(kind=UNCHANGED)
        impact = _make_impact_summary(transition=UNCHANGED, impact=MIXED_IMPACT)

        assessor = ResearchWorkspaceConsumerProjectionHealthTransitionAssessor()
        assessment = assessor.assess(transition, impact)

        assert assessment.assessment == ASSESSMENT_MIXED

    def test_improved_produces_improving_regardless_of_impact(self):
        # Transition kind takes precedence over impact classification.
        transition = _make_transition(kind=IMPROVED)
        impact = _make_impact_summary(transition=IMPROVED, impact=NEGATIVE)

        assessor = ResearchWorkspaceConsumerProjectionHealthTransitionAssessor()
        assessment = assessor.assess(transition, impact)

        assert assessment.assessment == IMPROVING

    def test_recovered_produces_recovered_even_with_mixed_impact(self):
        # Full recovery wins even if the signal-level impact is mixed.
        transition = _make_transition(kind=RECOVERED)
        impact = _make_impact_summary(transition=RECOVERED, impact=MIXED_IMPACT)

        assessor = ResearchWorkspaceConsumerProjectionHealthTransitionAssessor()
        assessment = assessor.assess(transition, impact)

        assert assessment.assessment == ASSESSMENT_RECOVERED

    def test_deteriorated_produces_deteriorating(self):
        transition = _make_transition(kind=DETERIORATED)
        impact = _make_impact_summary(transition=DETERIORATED, impact=NEGATIVE)

        assessor = ResearchWorkspaceConsumerProjectionHealthTransitionAssessor()
        assessment = assessor.assess(transition, impact)

        assert assessment.assessment == DETERIORATING

    def test_became_critical_produces_escalated_even_with_positive_impact(self):
        # Newly critical wins even if signal-level impact looks positive.
        transition = _make_transition(kind=BECAME_CRITICAL)
        impact = _make_impact_summary(transition=BECAME_CRITICAL, impact=POSITIVE)

        assessor = ResearchWorkspaceConsumerProjectionHealthTransitionAssessor()
        assessment = assessor.assess(transition, impact)

        assert assessment.assessment == ESCALATED


class TestRequiresAttention:
    """Test the derived requires_attention property."""

    def test_requires_attention_true_for_deteriorating(self):
        transition = _make_transition(kind=DETERIORATED)
        impact = _make_impact_summary(transition=DETERIORATED, impact=NEGATIVE)

        assessor = ResearchWorkspaceConsumerProjectionHealthTransitionAssessor()
        assessment = assessor.assess(transition, impact)

        assert assessment.requires_attention is True

    def test_requires_attention_true_for_escalated(self):
        transition = _make_transition(kind=BECAME_CRITICAL)
        impact = _make_impact_summary(transition=BECAME_CRITICAL, impact=NEGATIVE)

        assessor = ResearchWorkspaceConsumerProjectionHealthTransitionAssessor()
        assessment = assessor.assess(transition, impact)

        assert assessment.requires_attention is True

    def test_requires_attention_true_for_mixed(self):
        transition = _make_transition(kind=UNCHANGED)
        impact = _make_impact_summary(transition=UNCHANGED, impact=MIXED_IMPACT)

        assessor = ResearchWorkspaceConsumerProjectionHealthTransitionAssessor()
        assessment = assessor.assess(transition, impact)

        assert assessment.requires_attention is True

    def test_requires_attention_false_for_stable(self):
        transition = _make_transition(kind=UNCHANGED)
        impact = _make_impact_summary(transition=UNCHANGED, impact=NONE_IMPACT)

        assessor = ResearchWorkspaceConsumerProjectionHealthTransitionAssessor()
        assessment = assessor.assess(transition, impact)

        assert assessment.requires_attention is False

    def test_requires_attention_false_for_improving(self):
        transition = _make_transition(kind=IMPROVED)
        impact = _make_impact_summary(transition=IMPROVED, impact=POSITIVE)

        assessor = ResearchWorkspaceConsumerProjectionHealthTransitionAssessor()
        assessment = assessor.assess(transition, impact)

        assert assessment.requires_attention is False

    def test_requires_attention_false_for_recovered(self):
        transition = _make_transition(kind=RECOVERED)
        impact = _make_impact_summary(transition=RECOVERED, impact=POSITIVE)

        assessor = ResearchWorkspaceConsumerProjectionHealthTransitionAssessor()
        assessment = assessor.assess(transition, impact)

        assert assessment.requires_attention is False


class TestValidation:
    """Test rejection of misaligned artifacts."""

    def test_projection_mismatch_raises_error(self):
        transition = _make_transition(projection_name="workspace.bootstrap")
        impact = _make_impact_summary(projection_name="workspace.attention")

        assessor = ResearchWorkspaceConsumerProjectionHealthTransitionAssessor()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentError
        ):
            assessor.assess(transition, impact)

    def test_previous_execution_id_mismatch_raises_error(self):
        transition = _make_transition(previous_execution_id="exec-a")
        impact = _make_impact_summary(previous_execution_id="exec-b")

        assessor = ResearchWorkspaceConsumerProjectionHealthTransitionAssessor()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentError
        ):
            assessor.assess(transition, impact)

    def test_current_execution_id_mismatch_raises_error(self):
        transition = _make_transition(current_execution_id="exec-a")
        impact = _make_impact_summary(current_execution_id="exec-b")

        assessor = ResearchWorkspaceConsumerProjectionHealthTransitionAssessor()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentError
        ):
            assessor.assess(transition, impact)

    def test_transition_kind_mismatch_raises_error(self):
        transition = _make_transition(kind=IMPROVED)
        impact = _make_impact_summary(transition=DETERIORATED)

        assessor = ResearchWorkspaceConsumerProjectionHealthTransitionAssessor()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentError
        ):
            assessor.assess(transition, impact)


class TestIdentityPreservation:
    """Test identity fields are reused, not regenerated."""

    def test_identity_fields_are_preserved(self):
        transition = _make_transition(
            projection_name="workspace.attention",
            previous_execution_id="req-previous",
            current_execution_id="req-current",
            kind=DETERIORATED,
        )
        impact = _make_impact_summary(
            projection_name="workspace.attention",
            previous_execution_id="req-previous",
            current_execution_id="req-current",
            transition=DETERIORATED,
            impact=NEGATIVE,
        )

        assessor = ResearchWorkspaceConsumerProjectionHealthTransitionAssessor()
        assessment = assessor.assess(transition, impact)

        assert assessment.projection_name == "workspace.attention"
        assert assessment.previous_execution_id == "req-previous"
        assert assessment.current_execution_id == "req-current"
        assert assessment.transition == DETERIORATED
        assert assessment.impact == NEGATIVE


class TestDeterminism:
    """Test assessment resolution is deterministic."""

    def test_equivalent_inputs_produce_equivalent_assessments(self):
        transition = _make_transition(kind=BECAME_CRITICAL)
        impact = _make_impact_summary(transition=BECAME_CRITICAL, impact=NEGATIVE)

        assessor = ResearchWorkspaceConsumerProjectionHealthTransitionAssessor()

        assessment1 = assessor.assess(transition, impact)
        assessment2 = assessor.assess(transition, impact)

        assert assessment1 == assessment2


class TestArchitecturalBoundaries:
    """Test structural guarantees of the assessor."""

    def test_assessor_has_no_external_dependencies(self):
        assessor = ResearchWorkspaceConsumerProjectionHealthTransitionAssessor()

        assert assessor.__dict__ == {}

    def test_assessor_does_not_mutate_input_artifacts(self):
        transition = _make_transition(kind=BECAME_CRITICAL)
        impact = _make_impact_summary(transition=BECAME_CRITICAL, impact=NEGATIVE)

        transition_dict = transition.to_dict()
        impact_dict = impact.to_dict()

        assessor = ResearchWorkspaceConsumerProjectionHealthTransitionAssessor()
        assessor.assess(transition, impact)

        assert transition.to_dict() == transition_dict
        assert impact.to_dict() == impact_dict

    def test_assessor_works_from_artifacts_alone(self):
        # No receipt, quality signal, or explanation object is ever
        # constructed here - proves the assessor only needs the
        # transition and impact summary.
        transition = _make_transition(
            previous_execution_id="artifacts-only-previous",
            current_execution_id="artifacts-only-current",
            kind=RECOVERED,
        )
        impact = _make_impact_summary(
            previous_execution_id="artifacts-only-previous",
            current_execution_id="artifacts-only-current",
            transition=RECOVERED,
            impact=POSITIVE,
        )

        assessor = ResearchWorkspaceConsumerProjectionHealthTransitionAssessor()
        assessment = assessor.assess(transition, impact)

        assert assessment.assessment == ASSESSMENT_RECOVERED
