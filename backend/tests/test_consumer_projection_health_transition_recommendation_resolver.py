import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionHealthTransitionAssessment,
    ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind,
    ResearchWorkspaceConsumerProjectionHealthTransitionImpact,
    ResearchWorkspaceConsumerProjectionHealthTransitionKind,
    ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationKind,
    ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationResolver,
)


def _make_assessment(
    *,
    projection_name="workspace.bootstrap",
    previous_execution_id="exec-1",
    current_execution_id="exec-2",
    transition=ResearchWorkspaceConsumerProjectionHealthTransitionKind.UNCHANGED,
    impact=ResearchWorkspaceConsumerProjectionHealthTransitionImpact.NONE,
    assessment=ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind.STABLE,
):
    return ResearchWorkspaceConsumerProjectionHealthTransitionAssessment(
        projection_name=projection_name,
        previous_execution_id=previous_execution_id,
        current_execution_id=current_execution_id,
        transition=transition,
        impact=impact,
        assessment=assessment,
    )


STABLE = ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind.STABLE
IMPROVING = ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind.IMPROVING
RECOVERED = ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind.RECOVERED
DETERIORATING = ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind.DETERIORATING
ESCALATED = ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind.ESCALATED
MIXED = ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind.MIXED

NO_ACTION = ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationKind.NO_ACTION
CONTINUE_OBSERVATION = ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationKind.CONTINUE_OBSERVATION
REVIEW_CHANGES = ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationKind.REVIEW_CHANGES
INVESTIGATE = ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationKind.INVESTIGATE
PRIORITIZE_REVIEW = ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationKind.PRIORITIZE_REVIEW


class TestRecommendationMapping:
    """Test the deterministic assessment-to-recommendation mapping."""

    @pytest.mark.parametrize(
        "assessment_kind,expected_recommendation",
        [
            (STABLE, NO_ACTION),
            (IMPROVING, CONTINUE_OBSERVATION),
            (RECOVERED, NO_ACTION),
            (MIXED, REVIEW_CHANGES),
            (DETERIORATING, INVESTIGATE),
            (ESCALATED, PRIORITIZE_REVIEW),
        ],
    )
    def test_recommendation_mapping(
        self, assessment_kind, expected_recommendation
    ):
        assessment = _make_assessment(assessment=assessment_kind)

        resolver = ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationResolver()
        recommendation = resolver.resolve(assessment)

        assert recommendation.recommendation == expected_recommendation


class TestActionRecommended:
    """Test the derived action_recommended property."""

    @pytest.mark.parametrize(
        "assessment_kind",
        [STABLE, RECOVERED],
    )
    def test_action_recommended_false_for_no_action(self, assessment_kind):
        assessment = _make_assessment(assessment=assessment_kind)

        resolver = ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationResolver()
        recommendation = resolver.resolve(assessment)

        assert recommendation.action_recommended is False

    def test_action_recommended_false_for_continue_observation(self):
        assessment = _make_assessment(assessment=IMPROVING)

        resolver = ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationResolver()
        recommendation = resolver.resolve(assessment)

        assert recommendation.action_recommended is False

    @pytest.mark.parametrize(
        "assessment_kind",
        [MIXED, DETERIORATING, ESCALATED],
    )
    def test_action_recommended_true_for_review_investigate_prioritize(
        self, assessment_kind
    ):
        assessment = _make_assessment(assessment=assessment_kind)

        resolver = ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationResolver()
        recommendation = resolver.resolve(assessment)

        assert recommendation.action_recommended is True


class TestIdentityPreservation:
    """Test identity/assessment fields are reused, not regenerated."""

    def test_identity_fields_are_preserved(self):
        assessment = _make_assessment(
            projection_name="workspace.attention",
            previous_execution_id="req-previous",
            current_execution_id="req-current",
            assessment=ESCALATED,
        )

        resolver = ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationResolver()
        recommendation = resolver.resolve(assessment)

        assert recommendation.projection_name == "workspace.attention"
        assert recommendation.previous_execution_id == "req-previous"
        assert recommendation.current_execution_id == "req-current"
        assert recommendation.assessment == ESCALATED


class TestDeterminism:
    """Test recommendation resolution is deterministic."""

    def test_equivalent_assessments_produce_equivalent_recommendations(self):
        assessment = _make_assessment(assessment=DETERIORATING)

        resolver = ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationResolver()

        recommendation1 = resolver.resolve(assessment)
        recommendation2 = resolver.resolve(assessment)

        assert recommendation1 == recommendation2


class TestArchitecturalBoundaries:
    """Test structural guarantees of the resolver."""

    def test_resolver_has_no_external_dependencies(self):
        resolver = ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationResolver()

        assert resolver.__dict__ == {}

    def test_resolver_does_not_mutate_assessment(self):
        assessment = _make_assessment(assessment=MIXED)
        original_dict = assessment.to_dict()

        resolver = ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationResolver()
        resolver.resolve(assessment)

        assert assessment.to_dict() == original_dict

    def test_resolver_works_from_assessment_alone(self):
        # No receipt, quality signal, transition, or impact summary
        # object is ever constructed here beyond the assessment's own
        # embedded fields - proves the resolver only needs the
        # assessment.
        assessment = _make_assessment(
            previous_execution_id="assessment-only-previous",
            current_execution_id="assessment-only-current",
            assessment=RECOVERED,
        )

        resolver = ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationResolver()
        recommendation = resolver.resolve(assessment)

        assert recommendation.previous_execution_id == "assessment-only-previous"
        assert recommendation.recommendation == NO_ACTION
