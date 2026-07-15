import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionHealthTransitionAssessment,
    ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind,
    ResearchWorkspaceConsumerProjectionHealthTransitionImpact,
    ResearchWorkspaceConsumerProjectionHealthTransitionKind,
    ResearchWorkspaceConsumerProjectionHealthTransitionRecommendation,
    ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationKind,
    ResearchWorkspaceConsumerProjectionHealthTransitionResponseDirectiveBuilder,
    ResearchWorkspaceConsumerProjectionHealthTransitionResponseDirectiveError,
    ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanner,
    ResearchWorkspaceConsumerProjectionHealthTransitionResponsePriority,
    ResearchWorkspaceConsumerProjectionHealthTransitionResponsePriorityResult,
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


def _make_priority_result(
    *,
    projection_name="workspace.bootstrap",
    previous_execution_id="exec-1",
    current_execution_id="exec-2",
    recommendation=ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationKind.NO_ACTION,
    priority=ResearchWorkspaceConsumerProjectionHealthTransitionResponsePriority.NONE,
):
    return ResearchWorkspaceConsumerProjectionHealthTransitionResponsePriorityResult(
        projection_name=projection_name,
        previous_execution_id=previous_execution_id,
        current_execution_id=current_execution_id,
        recommendation=recommendation,
        priority=priority,
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


class _RecordingRecommendationResolver:
    def __init__(self, recommendation_to_return):
        self._recommendation_to_return = recommendation_to_return
        self.received_assessment = None

    def resolve(self, assessment):
        self.received_assessment = assessment
        return self._recommendation_to_return


class _RecordingPriorityResolver:
    def __init__(self, priority_to_return):
        self._priority_to_return = priority_to_return
        self.received_recommendation = None

    def resolve(self, recommendation):
        self.received_recommendation = recommendation
        return self._priority_to_return


class _RecordingDirectiveBuilder:
    def __init__(self, directive_to_return):
        self._directive_to_return = directive_to_return
        self.received_args = None

    def build(self, recommendation, priority):
        self.received_args = (recommendation, priority)
        return self._directive_to_return


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


class TestDirectiveBuilding:
    """Test basic directive construction from aligned artifacts."""

    def test_valid_inputs_produce_a_directive(self):
        recommendation = _make_recommendation(
            recommendation=INVESTIGATE
        )
        priority = _make_priority_result(
            recommendation=INVESTIGATE, priority=HIGH
        )

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponseDirectiveBuilder()
        directive = builder.build(recommendation, priority)

        assert directive.recommendation == INVESTIGATE
        assert directive.priority == HIGH

    def test_projection_name_is_preserved(self):
        recommendation = _make_recommendation(
            projection_name="workspace.attention"
        )
        priority = _make_priority_result(
            projection_name="workspace.attention"
        )

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponseDirectiveBuilder()
        directive = builder.build(recommendation, priority)

        assert directive.projection_name == "workspace.attention"

    def test_previous_execution_id_is_preserved(self):
        recommendation = _make_recommendation(previous_execution_id="req-previous")
        priority = _make_priority_result(previous_execution_id="req-previous")

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponseDirectiveBuilder()
        directive = builder.build(recommendation, priority)

        assert directive.previous_execution_id == "req-previous"

    def test_current_execution_id_is_preserved(self):
        recommendation = _make_recommendation(current_execution_id="req-current")
        priority = _make_priority_result(current_execution_id="req-current")

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponseDirectiveBuilder()
        directive = builder.build(recommendation, priority)

        assert directive.current_execution_id == "req-current"

    def test_recommendation_is_preserved(self):
        recommendation = _make_recommendation(recommendation=REVIEW_CHANGES)
        priority = _make_priority_result(
            recommendation=REVIEW_CHANGES, priority=MEDIUM
        )

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponseDirectiveBuilder()
        directive = builder.build(recommendation, priority)

        assert directive.recommendation == REVIEW_CHANGES

    def test_priority_is_preserved(self):
        recommendation = _make_recommendation(
            recommendation=PRIORITIZE_REVIEW
        )
        priority = _make_priority_result(
            recommendation=PRIORITIZE_REVIEW, priority=URGENT
        )

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponseDirectiveBuilder()
        directive = builder.build(recommendation, priority)

        assert directive.priority == URGENT


class TestActionRecommended:
    """Test the derived action_recommended property."""

    @pytest.mark.parametrize(
        "recommendation_kind,priority_kind,expected",
        [
            (NO_ACTION, NONE_PRIORITY, False),
            (CONTINUE_OBSERVATION, LOW, False),
            (REVIEW_CHANGES, MEDIUM, True),
            (INVESTIGATE, HIGH, True),
            (PRIORITIZE_REVIEW, URGENT, True),
        ],
    )
    def test_action_recommended(
        self, recommendation_kind, priority_kind, expected
    ):
        recommendation = _make_recommendation(recommendation=recommendation_kind)
        priority = _make_priority_result(
            recommendation=recommendation_kind, priority=priority_kind
        )

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponseDirectiveBuilder()
        directive = builder.build(recommendation, priority)

        assert directive.action_recommended is expected


class TestValidation:
    """Test rejection of misaligned artifacts."""

    def test_projection_mismatch_raises_error(self):
        recommendation = _make_recommendation(projection_name="workspace.bootstrap")
        priority = _make_priority_result(projection_name="workspace.attention")

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponseDirectiveBuilder()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionHealthTransitionResponseDirectiveError
        ):
            builder.build(recommendation, priority)

    def test_previous_execution_id_mismatch_raises_error(self):
        recommendation = _make_recommendation(previous_execution_id="exec-a")
        priority = _make_priority_result(previous_execution_id="exec-b")

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponseDirectiveBuilder()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionHealthTransitionResponseDirectiveError
        ):
            builder.build(recommendation, priority)

    def test_current_execution_id_mismatch_raises_error(self):
        recommendation = _make_recommendation(current_execution_id="exec-a")
        priority = _make_priority_result(current_execution_id="exec-b")

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponseDirectiveBuilder()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionHealthTransitionResponseDirectiveError
        ):
            builder.build(recommendation, priority)

    def test_recommendation_mismatch_raises_error(self):
        recommendation = _make_recommendation(recommendation=INVESTIGATE)
        priority = _make_priority_result(recommendation=PRIORITIZE_REVIEW)

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponseDirectiveBuilder()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionHealthTransitionResponseDirectiveError
        ):
            builder.build(recommendation, priority)


class TestDeterminism:
    """Test directive building is deterministic."""

    def test_equivalent_inputs_produce_equivalent_directives(self):
        recommendation = _make_recommendation(recommendation=INVESTIGATE)
        priority = _make_priority_result(
            recommendation=INVESTIGATE, priority=HIGH
        )

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponseDirectiveBuilder()

        directive1 = builder.build(recommendation, priority)
        directive2 = builder.build(recommendation, priority)

        assert directive1 == directive2


class TestArchitecturalBoundaries:
    """Test structural guarantees of the builder."""

    def test_builder_has_no_external_dependencies(self):
        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponseDirectiveBuilder()

        assert builder.__dict__ == {}

    def test_builder_does_not_mutate_input_artifacts(self):
        recommendation = _make_recommendation(recommendation=INVESTIGATE)
        priority = _make_priority_result(
            recommendation=INVESTIGATE, priority=HIGH
        )

        recommendation_dict = recommendation.to_dict()
        priority_dict = priority.to_dict()

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponseDirectiveBuilder()
        builder.build(recommendation, priority)

        assert recommendation.to_dict() == recommendation_dict
        assert priority.to_dict() == priority_dict

    def test_builder_works_from_artifacts_alone(self):
        # No receipt, quality signal, transition, impact summary, or
        # assessment object is ever constructed here beyond the two
        # inputs' own embedded fields - proves the builder only needs
        # the recommendation and priority result.
        recommendation = _make_recommendation(
            previous_execution_id="artifacts-only-previous",
            current_execution_id="artifacts-only-current",
            recommendation=PRIORITIZE_REVIEW,
        )
        priority = _make_priority_result(
            previous_execution_id="artifacts-only-previous",
            current_execution_id="artifacts-only-current",
            recommendation=PRIORITIZE_REVIEW,
            priority=URGENT,
        )

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponseDirectiveBuilder()
        directive = builder.build(recommendation, priority)

        assert directive.priority == URGENT
        assert directive.action_recommended is True


class TestResponsePlanner:
    """Test the optional assessment-to-directive composition planner."""

    def test_planner_delegates_to_existing_services(self):
        assessment = _make_assessment()

        fake_recommendation = _make_recommendation(recommendation=REVIEW_CHANGES)
        fake_priority = _make_priority_result(
            recommendation=REVIEW_CHANGES, priority=MEDIUM
        )
        fake_directive = object()

        recommendation_resolver = _RecordingRecommendationResolver(
            recommendation_to_return=fake_recommendation
        )
        priority_resolver = _RecordingPriorityResolver(
            priority_to_return=fake_priority
        )
        directive_builder = _RecordingDirectiveBuilder(
            directive_to_return=fake_directive
        )

        planner = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanner(
            recommendation_resolver=recommendation_resolver,
            priority_resolver=priority_resolver,
            directive_builder=directive_builder,
        )

        result = planner.plan(assessment)

        assert recommendation_resolver.received_assessment is assessment
        assert priority_resolver.received_recommendation is fake_recommendation
        assert directive_builder.received_args == (
            fake_recommendation,
            fake_priority,
        )
        assert result is fake_directive

    def test_planner_does_not_duplicate_mapping_logic(self):
        assessment = _make_assessment(
            assessment=ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind.ESCALATED
        )

        planner = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanner()
        actual = planner.plan(assessment)

        expected_recommendation = planner._recommendation_resolver.resolve(
            assessment
        )
        expected_priority = planner._priority_resolver.resolve(
            expected_recommendation
        )
        expected = planner._directive_builder.build(
            expected_recommendation, expected_priority
        )

        assert actual == expected

    def test_planner_uses_default_services_when_not_provided(self):
        assessment = _make_assessment(
            assessment=ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind.ESCALATED
        )

        planner = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanner()
        directive = planner.plan(assessment)

        assert directive.recommendation == PRIORITIZE_REVIEW
        assert directive.priority == URGENT
        assert directive.action_recommended is True
