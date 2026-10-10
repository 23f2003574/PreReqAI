import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionReadinessAssessment,
    ResearchWorkspaceConsumerProjectionReadinessDirectiveBuilder,
    ResearchWorkspaceConsumerProjectionReadinessDirectiveError,
    ResearchWorkspaceConsumerProjectionReadinessPriority,
    ResearchWorkspaceConsumerProjectionReadinessPriorityReport,
    ResearchWorkspaceConsumerProjectionReadinessRecommendation,
    ResearchWorkspaceConsumerProjectionReadinessRecommendationReport,
)


NO_ACTION = (
    ResearchWorkspaceConsumerProjectionReadinessRecommendation.NO_ACTION
)
INVESTIGATE = (
    ResearchWorkspaceConsumerProjectionReadinessRecommendation.INVESTIGATE
)
UNBLOCK_EXECUTION = (
    ResearchWorkspaceConsumerProjectionReadinessRecommendation.UNBLOCK_EXECUTION
)

NONE_PRIORITY = ResearchWorkspaceConsumerProjectionReadinessPriority.NONE
HIGH = ResearchWorkspaceConsumerProjectionReadinessPriority.HIGH
CRITICAL = ResearchWorkspaceConsumerProjectionReadinessPriority.CRITICAL


def _make_recommendation(
    *,
    projection_name="workspace.bootstrap",
    recommendation=NO_ACTION,
):
    return ResearchWorkspaceConsumerProjectionReadinessRecommendationReport(
        projection_name=projection_name,
        assessment=ResearchWorkspaceConsumerProjectionReadinessAssessment.STABLE,
        recommendation=recommendation,
    )


def _make_priority(
    *,
    projection_name="workspace.bootstrap",
    recommendation=NO_ACTION,
    priority=NONE_PRIORITY,
):
    return ResearchWorkspaceConsumerProjectionReadinessPriorityReport(
        projection_name=projection_name,
        recommendation=recommendation,
        priority=priority,
    )


class TestDirectiveBuilding:
    """A valid recommendation/priority pair builds a directive."""

    def test_valid_directive_built(self):
        recommendation = _make_recommendation(recommendation=NO_ACTION)
        priority = _make_priority(
            recommendation=NO_ACTION,
            priority=NONE_PRIORITY,
        )

        builder = ResearchWorkspaceConsumerProjectionReadinessDirectiveBuilder()
        directive = builder.build(recommendation, priority)

        assert directive.projection_name == "workspace.bootstrap"
        assert directive.recommendation == NO_ACTION
        assert directive.priority == NONE_PRIORITY


class TestRecommendationPreserved:
    """The recommendation is copied, not resolved again."""

    def test_recommendation_is_preserved(self):
        recommendation = _make_recommendation(recommendation=INVESTIGATE)
        priority = _make_priority(recommendation=INVESTIGATE, priority=HIGH)

        builder = ResearchWorkspaceConsumerProjectionReadinessDirectiveBuilder()
        directive = builder.build(recommendation, priority)

        assert directive.recommendation == INVESTIGATE


class TestPriorityPreserved:
    """The priority is copied, not resolved again."""

    def test_priority_is_preserved(self):
        recommendation = _make_recommendation(
            recommendation=UNBLOCK_EXECUTION
        )
        priority = _make_priority(
            recommendation=UNBLOCK_EXECUTION,
            priority=CRITICAL,
        )

        builder = ResearchWorkspaceConsumerProjectionReadinessDirectiveBuilder()
        directive = builder.build(recommendation, priority)

        assert directive.priority == CRITICAL


class TestActionRequiredDerivation:
    """action_required follows the recommendation, not the priority."""

    def test_no_action_produces_action_required_false(self):
        recommendation = _make_recommendation(recommendation=NO_ACTION)
        priority = _make_priority(
            recommendation=NO_ACTION,
            priority=NONE_PRIORITY,
        )

        builder = ResearchWorkspaceConsumerProjectionReadinessDirectiveBuilder()
        directive = builder.build(recommendation, priority)

        assert directive.action_required is False

    def test_investigate_produces_action_required_true(self):
        recommendation = _make_recommendation(recommendation=INVESTIGATE)
        priority = _make_priority(recommendation=INVESTIGATE, priority=HIGH)

        builder = ResearchWorkspaceConsumerProjectionReadinessDirectiveBuilder()
        directive = builder.build(recommendation, priority)

        assert directive.action_required is True

    def test_unblock_execution_produces_action_required_true(self):
        recommendation = _make_recommendation(
            recommendation=UNBLOCK_EXECUTION
        )
        priority = _make_priority(
            recommendation=UNBLOCK_EXECUTION,
            priority=CRITICAL,
        )

        builder = ResearchWorkspaceConsumerProjectionReadinessDirectiveBuilder()
        directive = builder.build(recommendation, priority)

        assert directive.action_required is True


class TestProjectionMismatch:
    """A recommendation/priority pair for different projections is rejected."""

    def test_projection_mismatch_raises_error(self):
        recommendation = _make_recommendation(
            projection_name="workspace.bootstrap"
        )
        priority = _make_priority(projection_name="workspace.attention")

        builder = ResearchWorkspaceConsumerProjectionReadinessDirectiveBuilder()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionReadinessDirectiveError
        ):
            builder.build(recommendation, priority)


class TestRecommendationMismatch:
    """A priority report resolved from a different recommendation is rejected."""

    def test_recommendation_mismatch_raises_error(self):
        recommendation = _make_recommendation(recommendation=NO_ACTION)
        priority = _make_priority(
            recommendation=UNBLOCK_EXECUTION,
            priority=CRITICAL,
        )

        builder = ResearchWorkspaceConsumerProjectionReadinessDirectiveBuilder()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionReadinessDirectiveError
        ):
            builder.build(recommendation, priority)


class TestDeterminism:
    """Building the same pair twice yields equal directives."""

    def test_equivalent_inputs_produce_equivalent_directives(self):
        recommendation = _make_recommendation(recommendation=INVESTIGATE)
        priority = _make_priority(recommendation=INVESTIGATE, priority=HIGH)

        builder = ResearchWorkspaceConsumerProjectionReadinessDirectiveBuilder()

        first = builder.build(recommendation, priority)
        second = builder.build(recommendation, priority)

        assert first == second


class TestArchitecturalBoundaries:
    """Structural guarantees: no state, no mutation, no side effects."""

    def test_builder_has_no_external_dependencies(self):
        builder = ResearchWorkspaceConsumerProjectionReadinessDirectiveBuilder()

        assert builder.__dict__ == {}

    def test_builder_does_not_mutate_inputs(self):
        recommendation = _make_recommendation(recommendation=INVESTIGATE)
        priority = _make_priority(recommendation=INVESTIGATE, priority=HIGH)

        recommendation_dict = recommendation.to_dict()
        priority_dict = priority.to_dict()

        builder = ResearchWorkspaceConsumerProjectionReadinessDirectiveBuilder()
        builder.build(recommendation, priority)

        assert recommendation.to_dict() == recommendation_dict
        assert priority.to_dict() == priority_dict

    def test_directive_carries_no_workflow_or_scheduling_state(self):
        recommendation = _make_recommendation(recommendation=NO_ACTION)
        priority = _make_priority(
            recommendation=NO_ACTION,
            priority=NONE_PRIORITY,
        )

        builder = ResearchWorkspaceConsumerProjectionReadinessDirectiveBuilder()
        directive = builder.build(recommendation, priority)

        assert set(directive.to_dict().keys()) == {
            "projection_name",
            "recommendation",
            "priority",
            "action_required",
        }
