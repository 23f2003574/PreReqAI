from backend.session import (
    ResearchWorkspaceConsumerProjectionReadinessAssessment,
    ResearchWorkspaceConsumerProjectionReadinessAssessmentReport,
    ResearchWorkspaceConsumerProjectionReadinessImpact,
    ResearchWorkspaceConsumerProjectionReadinessRecommendation,
    ResearchWorkspaceConsumerProjectionReadinessRecommendationResolver,
    ResearchWorkspaceConsumerProjectionReadinessTransition,
)


STABLE = ResearchWorkspaceConsumerProjectionReadinessAssessment.STABLE
IMPROVING = ResearchWorkspaceConsumerProjectionReadinessAssessment.IMPROVING
RECOVERED = ResearchWorkspaceConsumerProjectionReadinessAssessment.RECOVERED
DETERIORATING = (
    ResearchWorkspaceConsumerProjectionReadinessAssessment.DETERIORATING
)
BLOCKED_ASSESSMENT = (
    ResearchWorkspaceConsumerProjectionReadinessAssessment.BLOCKED
)
MIXED_ASSESSMENT = (
    ResearchWorkspaceConsumerProjectionReadinessAssessment.MIXED
)

NO_ACTION = (
    ResearchWorkspaceConsumerProjectionReadinessRecommendation.NO_ACTION
)
CONTINUE_MONITORING = (
    ResearchWorkspaceConsumerProjectionReadinessRecommendation.CONTINUE_MONITORING
)
REVIEW_CHANGES = (
    ResearchWorkspaceConsumerProjectionReadinessRecommendation.REVIEW_CHANGES
)
INVESTIGATE = (
    ResearchWorkspaceConsumerProjectionReadinessRecommendation.INVESTIGATE
)
UNBLOCK_EXECUTION = (
    ResearchWorkspaceConsumerProjectionReadinessRecommendation.UNBLOCK_EXECUTION
)

UNCHANGED = ResearchWorkspaceConsumerProjectionReadinessTransition.UNCHANGED
NONE_IMPACT = ResearchWorkspaceConsumerProjectionReadinessImpact.NONE


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


class TestResolutionMapping:
    """Test the full assessment -> recommendation mapping."""

    def test_stable_produces_no_action(self):
        assessment = _make_assessment(assessment=STABLE)

        resolver = (
            ResearchWorkspaceConsumerProjectionReadinessRecommendationResolver()
        )
        recommendation = resolver.resolve(assessment)

        assert recommendation.recommendation == NO_ACTION

    def test_improving_produces_continue_monitoring(self):
        assessment = _make_assessment(assessment=IMPROVING)

        resolver = (
            ResearchWorkspaceConsumerProjectionReadinessRecommendationResolver()
        )
        recommendation = resolver.resolve(assessment)

        assert recommendation.recommendation == CONTINUE_MONITORING

    def test_recovered_produces_no_action(self):
        assessment = _make_assessment(assessment=RECOVERED)

        resolver = (
            ResearchWorkspaceConsumerProjectionReadinessRecommendationResolver()
        )
        recommendation = resolver.resolve(assessment)

        assert recommendation.recommendation == NO_ACTION

    def test_mixed_produces_review_changes(self):
        assessment = _make_assessment(assessment=MIXED_ASSESSMENT)

        resolver = (
            ResearchWorkspaceConsumerProjectionReadinessRecommendationResolver()
        )
        recommendation = resolver.resolve(assessment)

        assert recommendation.recommendation == REVIEW_CHANGES

    def test_deteriorating_produces_investigate(self):
        assessment = _make_assessment(assessment=DETERIORATING)

        resolver = (
            ResearchWorkspaceConsumerProjectionReadinessRecommendationResolver()
        )
        recommendation = resolver.resolve(assessment)

        assert recommendation.recommendation == INVESTIGATE

    def test_blocked_produces_unblock_execution(self):
        assessment = _make_assessment(assessment=BLOCKED_ASSESSMENT)

        resolver = (
            ResearchWorkspaceConsumerProjectionReadinessRecommendationResolver()
        )
        recommendation = resolver.resolve(assessment)

        assert recommendation.recommendation == UNBLOCK_EXECUTION


class TestActionRequiredProperty:
    """Test the derived action_required property."""

    def test_action_required_true_for_review_changes(self):
        assessment = _make_assessment(assessment=MIXED_ASSESSMENT)

        resolver = (
            ResearchWorkspaceConsumerProjectionReadinessRecommendationResolver()
        )
        recommendation = resolver.resolve(assessment)

        assert recommendation.action_required is True

    def test_action_required_true_for_investigate(self):
        assessment = _make_assessment(assessment=DETERIORATING)

        resolver = (
            ResearchWorkspaceConsumerProjectionReadinessRecommendationResolver()
        )
        recommendation = resolver.resolve(assessment)

        assert recommendation.action_required is True

    def test_action_required_true_for_unblock_execution(self):
        assessment = _make_assessment(assessment=BLOCKED_ASSESSMENT)

        resolver = (
            ResearchWorkspaceConsumerProjectionReadinessRecommendationResolver()
        )
        recommendation = resolver.resolve(assessment)

        assert recommendation.action_required is True

    def test_action_required_false_for_no_action(self):
        assessment = _make_assessment(assessment=STABLE)

        resolver = (
            ResearchWorkspaceConsumerProjectionReadinessRecommendationResolver()
        )
        recommendation = resolver.resolve(assessment)

        assert recommendation.action_required is False

    def test_action_required_false_for_continue_monitoring(self):
        assessment = _make_assessment(assessment=IMPROVING)

        resolver = (
            ResearchWorkspaceConsumerProjectionReadinessRecommendationResolver()
        )
        recommendation = resolver.resolve(assessment)

        assert recommendation.action_required is False


class TestAssessmentPreserved:
    """projection_name and assessment are copied, not recomputed."""

    def test_identity_fields_are_preserved(self):
        assessment = _make_assessment(
            projection_name="workspace.attention",
            assessment=DETERIORATING,
        )

        resolver = (
            ResearchWorkspaceConsumerProjectionReadinessRecommendationResolver()
        )
        recommendation = resolver.resolve(assessment)

        assert recommendation.projection_name == "workspace.attention"
        assert recommendation.assessment == DETERIORATING


class TestDeterminism:
    """Resolving the same assessment twice yields equal recommendations."""

    def test_equivalent_assessments_produce_equivalent_recommendations(
        self,
    ):
        assessment = _make_assessment(assessment=BLOCKED_ASSESSMENT)

        resolver = (
            ResearchWorkspaceConsumerProjectionReadinessRecommendationResolver()
        )

        first = resolver.resolve(assessment)
        second = resolver.resolve(assessment)

        assert first == second


class TestArchitecturalBoundaries:
    """Structural guarantees: no state, no mutation, no side effects."""

    def test_resolver_has_no_external_dependencies(self):
        resolver = (
            ResearchWorkspaceConsumerProjectionReadinessRecommendationResolver()
        )

        assert resolver.__dict__ == {}

    def test_resolver_does_not_mutate_assessment(self):
        assessment = _make_assessment(assessment=DETERIORATING)

        assessment_dict_before = assessment.to_dict()

        resolver = (
            ResearchWorkspaceConsumerProjectionReadinessRecommendationResolver()
        )
        resolver.resolve(assessment)

        assert assessment.to_dict() == assessment_dict_before

    def test_recommendation_carries_no_priority_or_scheduling(self):
        assessment = _make_assessment(assessment=STABLE)

        resolver = (
            ResearchWorkspaceConsumerProjectionReadinessRecommendationResolver()
        )
        recommendation = resolver.resolve(assessment)

        assert set(recommendation.to_dict().keys()) == {
            "projection_name",
            "assessment",
            "recommendation",
            "action_required",
        }
