import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionHealthTransitionRecommendation,
    ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationKind,
    ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind,
    ResearchWorkspaceConsumerProjectionHealthTransitionResponsePriority,
    ResearchWorkspaceConsumerProjectionHealthTransitionResponsePriorityResolver,
)


def _make_recommendation(
    *,
    projection_name="workspace.bootstrap",
    previous_execution_id="exec-1",
    current_execution_id="exec-2",
    assessment=ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind.STABLE,
    recommendation=ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationKind.NO_ACTION,
):
    return ResearchWorkspaceConsumerProjectionHealthTransitionRecommendation(
        projection_name=projection_name,
        previous_execution_id=previous_execution_id,
        current_execution_id=current_execution_id,
        assessment=assessment,
        recommendation=recommendation,
    )


NO_ACTION = ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationKind.NO_ACTION
CONTINUE_OBSERVATION = ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationKind.CONTINUE_OBSERVATION
REVIEW_CHANGES = ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationKind.REVIEW_CHANGES
INVESTIGATE = ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationKind.INVESTIGATE
PRIORITIZE_REVIEW = ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationKind.PRIORITIZE_REVIEW

NONE_PRIORITY = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePriority.NONE
LOW = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePriority.LOW
MEDIUM = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePriority.MEDIUM
HIGH = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePriority.HIGH
URGENT = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePriority.URGENT


class TestPriorityMapping:
    """Test the deterministic recommendation-to-priority mapping."""

    @pytest.mark.parametrize(
        "recommendation_kind,expected_priority",
        [
            (NO_ACTION, NONE_PRIORITY),
            (CONTINUE_OBSERVATION, LOW),
            (REVIEW_CHANGES, MEDIUM),
            (INVESTIGATE, HIGH),
            (PRIORITIZE_REVIEW, URGENT),
        ],
    )
    def test_priority_mapping(self, recommendation_kind, expected_priority):
        recommendation = _make_recommendation(recommendation=recommendation_kind)

        resolver = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePriorityResolver()
        result = resolver.resolve(recommendation)

        assert result.priority == expected_priority


class TestPrioritized:
    """Test the derived prioritized property."""

    @pytest.mark.parametrize(
        "recommendation_kind",
        [NO_ACTION, CONTINUE_OBSERVATION],
    )
    def test_prioritized_false_for_none_and_low(self, recommendation_kind):
        recommendation = _make_recommendation(recommendation=recommendation_kind)

        resolver = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePriorityResolver()
        result = resolver.resolve(recommendation)

        assert result.prioritized is False

    @pytest.mark.parametrize(
        "recommendation_kind",
        [REVIEW_CHANGES, INVESTIGATE, PRIORITIZE_REVIEW],
    )
    def test_prioritized_true_for_medium_high_urgent(self, recommendation_kind):
        recommendation = _make_recommendation(recommendation=recommendation_kind)

        resolver = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePriorityResolver()
        result = resolver.resolve(recommendation)

        assert result.prioritized is True


class TestIdentityPreservation:
    """Test identity/recommendation fields are reused, not regenerated."""

    def test_identity_fields_are_preserved(self):
        recommendation = _make_recommendation(
            projection_name="workspace.attention",
            previous_execution_id="req-previous",
            current_execution_id="req-current",
            recommendation=PRIORITIZE_REVIEW,
        )

        resolver = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePriorityResolver()
        result = resolver.resolve(recommendation)

        assert result.projection_name == "workspace.attention"
        assert result.previous_execution_id == "req-previous"
        assert result.current_execution_id == "req-current"
        assert result.recommendation == PRIORITIZE_REVIEW


class TestDeterminism:
    """Test priority resolution is deterministic."""

    def test_equivalent_recommendations_produce_equivalent_priorities(self):
        recommendation = _make_recommendation(recommendation=INVESTIGATE)

        resolver = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePriorityResolver()

        result1 = resolver.resolve(recommendation)
        result2 = resolver.resolve(recommendation)

        assert result1 == result2


class TestArchitecturalBoundaries:
    """Test structural guarantees of the resolver."""

    def test_resolver_has_no_external_dependencies(self):
        resolver = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePriorityResolver()

        assert resolver.__dict__ == {}

    def test_resolver_does_not_mutate_recommendation(self):
        recommendation = _make_recommendation(recommendation=REVIEW_CHANGES)
        original_dict = recommendation.to_dict()

        resolver = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePriorityResolver()
        resolver.resolve(recommendation)

        assert recommendation.to_dict() == original_dict

    def test_resolver_works_from_recommendation_alone(self):
        # No receipt, quality signal, transition, impact summary, or
        # assessment object is ever constructed here beyond the
        # recommendation's own embedded fields - proves the resolver
        # only needs the recommendation.
        recommendation = _make_recommendation(
            previous_execution_id="recommendation-only-previous",
            current_execution_id="recommendation-only-current",
            recommendation=PRIORITIZE_REVIEW,
        )

        resolver = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePriorityResolver()
        result = resolver.resolve(recommendation)

        assert result.previous_execution_id == "recommendation-only-previous"
        assert result.priority == URGENT
