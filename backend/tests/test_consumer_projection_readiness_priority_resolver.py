from backend.session import (
    ResearchWorkspaceConsumerProjectionReadinessAssessment,
    ResearchWorkspaceConsumerProjectionReadinessPriority,
    ResearchWorkspaceConsumerProjectionReadinessPriorityResolver,
    ResearchWorkspaceConsumerProjectionReadinessRecommendation,
    ResearchWorkspaceConsumerProjectionReadinessRecommendationReport,
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

NONE_PRIORITY = ResearchWorkspaceConsumerProjectionReadinessPriority.NONE
LOW = ResearchWorkspaceConsumerProjectionReadinessPriority.LOW
MEDIUM = ResearchWorkspaceConsumerProjectionReadinessPriority.MEDIUM
HIGH = ResearchWorkspaceConsumerProjectionReadinessPriority.HIGH
CRITICAL = ResearchWorkspaceConsumerProjectionReadinessPriority.CRITICAL


def _make_recommendation(
    *,
    projection_name="workspace.bootstrap",
    assessment=ResearchWorkspaceConsumerProjectionReadinessAssessment.STABLE,
    recommendation=NO_ACTION,
):
    return ResearchWorkspaceConsumerProjectionReadinessRecommendationReport(
        projection_name=projection_name,
        assessment=assessment,
        recommendation=recommendation,
    )


class TestPriorityMapping:
    """Test the full recommendation -> priority mapping."""

    def test_no_action_produces_none(self):
        recommendation = _make_recommendation(recommendation=NO_ACTION)

        resolver = (
            ResearchWorkspaceConsumerProjectionReadinessPriorityResolver()
        )
        priority_report = resolver.resolve(recommendation)

        assert priority_report.priority == NONE_PRIORITY

    def test_continue_monitoring_produces_low(self):
        recommendation = _make_recommendation(
            recommendation=CONTINUE_MONITORING
        )

        resolver = (
            ResearchWorkspaceConsumerProjectionReadinessPriorityResolver()
        )
        priority_report = resolver.resolve(recommendation)

        assert priority_report.priority == LOW

    def test_review_changes_produces_medium(self):
        recommendation = _make_recommendation(recommendation=REVIEW_CHANGES)

        resolver = (
            ResearchWorkspaceConsumerProjectionReadinessPriorityResolver()
        )
        priority_report = resolver.resolve(recommendation)

        assert priority_report.priority == MEDIUM

    def test_investigate_produces_high(self):
        recommendation = _make_recommendation(recommendation=INVESTIGATE)

        resolver = (
            ResearchWorkspaceConsumerProjectionReadinessPriorityResolver()
        )
        priority_report = resolver.resolve(recommendation)

        assert priority_report.priority == HIGH

    def test_unblock_execution_produces_critical(self):
        recommendation = _make_recommendation(
            recommendation=UNBLOCK_EXECUTION
        )

        resolver = (
            ResearchWorkspaceConsumerProjectionReadinessPriorityResolver()
        )
        priority_report = resolver.resolve(recommendation)

        assert priority_report.priority == CRITICAL


class TestPrioritizedProperty:
    """Test the derived prioritized property."""

    def test_prioritized_false_for_none(self):
        recommendation = _make_recommendation(recommendation=NO_ACTION)

        resolver = (
            ResearchWorkspaceConsumerProjectionReadinessPriorityResolver()
        )
        priority_report = resolver.resolve(recommendation)

        assert priority_report.prioritized is False

    def test_prioritized_false_for_low(self):
        recommendation = _make_recommendation(
            recommendation=CONTINUE_MONITORING
        )

        resolver = (
            ResearchWorkspaceConsumerProjectionReadinessPriorityResolver()
        )
        priority_report = resolver.resolve(recommendation)

        assert priority_report.prioritized is False

    def test_prioritized_true_for_medium(self):
        recommendation = _make_recommendation(recommendation=REVIEW_CHANGES)

        resolver = (
            ResearchWorkspaceConsumerProjectionReadinessPriorityResolver()
        )
        priority_report = resolver.resolve(recommendation)

        assert priority_report.prioritized is True

    def test_prioritized_true_for_high(self):
        recommendation = _make_recommendation(recommendation=INVESTIGATE)

        resolver = (
            ResearchWorkspaceConsumerProjectionReadinessPriorityResolver()
        )
        priority_report = resolver.resolve(recommendation)

        assert priority_report.prioritized is True

    def test_prioritized_true_for_critical(self):
        recommendation = _make_recommendation(
            recommendation=UNBLOCK_EXECUTION
        )

        resolver = (
            ResearchWorkspaceConsumerProjectionReadinessPriorityResolver()
        )
        priority_report = resolver.resolve(recommendation)

        assert priority_report.prioritized is True


class TestRecommendationPreserved:
    """projection_name and recommendation are copied, not recomputed."""

    def test_identity_fields_are_preserved(self):
        recommendation = _make_recommendation(
            projection_name="workspace.attention",
            recommendation=INVESTIGATE,
        )

        resolver = (
            ResearchWorkspaceConsumerProjectionReadinessPriorityResolver()
        )
        priority_report = resolver.resolve(recommendation)

        assert priority_report.projection_name == "workspace.attention"
        assert priority_report.recommendation == INVESTIGATE


class TestDeterminism:
    """Resolving the same recommendation twice yields equal priorities."""

    def test_equivalent_recommendations_produce_equivalent_priorities(
        self,
    ):
        recommendation = _make_recommendation(
            recommendation=UNBLOCK_EXECUTION
        )

        resolver = (
            ResearchWorkspaceConsumerProjectionReadinessPriorityResolver()
        )

        first = resolver.resolve(recommendation)
        second = resolver.resolve(recommendation)

        assert first == second


class TestArchitecturalBoundaries:
    """Structural guarantees: no state, no mutation, no side effects."""

    def test_resolver_has_no_external_dependencies(self):
        resolver = (
            ResearchWorkspaceConsumerProjectionReadinessPriorityResolver()
        )

        assert resolver.__dict__ == {}

    def test_resolver_does_not_mutate_recommendation(self):
        recommendation = _make_recommendation(recommendation=INVESTIGATE)

        recommendation_dict_before = recommendation.to_dict()

        resolver = (
            ResearchWorkspaceConsumerProjectionReadinessPriorityResolver()
        )
        resolver.resolve(recommendation)

        assert recommendation.to_dict() == recommendation_dict_before

    def test_priority_report_carries_no_scheduling_or_notification(self):
        recommendation = _make_recommendation(recommendation=NO_ACTION)

        resolver = (
            ResearchWorkspaceConsumerProjectionReadinessPriorityResolver()
        )
        priority_report = resolver.resolve(recommendation)

        assert set(priority_report.to_dict().keys()) == {
            "projection_name",
            "recommendation",
            "priority",
            "prioritized",
        }
