import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionHealthTransitionAssessment,
    ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind,
    ResearchWorkspaceConsumerProjectionHealthTransitionImpact,
    ResearchWorkspaceConsumerProjectionHealthTransitionKind,
    ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationKind,
    ResearchWorkspaceConsumerProjectionHealthTransitionResponseDirective,
    ResearchWorkspaceConsumerProjectionHealthTransitionResponsePackageBuilder,
    ResearchWorkspaceConsumerProjectionHealthTransitionResponsePackageError,
    ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanner,
    ResearchWorkspaceConsumerProjectionHealthTransitionResponsePriority,
    ResearchWorkspaceConsumerProjectionHealthTransitionResponseRationale,
    ResearchWorkspaceConsumerProjectionHealthTransitionResponseReason,
)


def _make_directive(
    *,
    projection_name="workspace.bootstrap",
    previous_execution_id="exec-1",
    current_execution_id="exec-2",
    recommendation=ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationKind.NO_ACTION,
    priority=ResearchWorkspaceConsumerProjectionHealthTransitionResponsePriority.NONE,
):
    return ResearchWorkspaceConsumerProjectionHealthTransitionResponseDirective(
        projection_name=projection_name,
        previous_execution_id=previous_execution_id,
        current_execution_id=current_execution_id,
        recommendation=recommendation,
        priority=priority,
    )


def _make_rationale(
    *,
    projection_name="workspace.bootstrap",
    previous_execution_id="exec-1",
    current_execution_id="exec-2",
    reason=ResearchWorkspaceConsumerProjectionHealthTransitionResponseReason.HEALTH_STABLE,
    recommendation=ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationKind.NO_ACTION,
    priority=ResearchWorkspaceConsumerProjectionHealthTransitionResponsePriority.NONE,
    summary="Execution health remained stable.",
):
    return ResearchWorkspaceConsumerProjectionHealthTransitionResponseRationale(
        projection_name=projection_name,
        previous_execution_id=previous_execution_id,
        current_execution_id=current_execution_id,
        reason=reason,
        recommendation=recommendation,
        priority=priority,
        summary=summary,
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


class _RecordingRationaleBuilder:
    def __init__(self, rationale_to_return):
        self._rationale_to_return = rationale_to_return
        self.received_args = None

    def build(self, assessment, directive):
        self.received_args = (assessment, directive)
        return self._rationale_to_return


class _RecordingPackageBuilder:
    def __init__(self, package_to_return):
        self._package_to_return = package_to_return
        self.received_args = None

    def build(self, directive, rationale):
        self.received_args = (directive, rationale)
        return self._package_to_return


NO_ACTION = ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationKind.NO_ACTION
INVESTIGATE = ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationKind.INVESTIGATE
PRIORITIZE_REVIEW = ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationKind.PRIORITIZE_REVIEW

NONE_PRIORITY = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePriority.NONE
HIGH = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePriority.HIGH
URGENT = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePriority.URGENT

HEALTH_STABLE = ResearchWorkspaceConsumerProjectionHealthTransitionResponseReason.HEALTH_STABLE
HEALTH_DETERIORATING = ResearchWorkspaceConsumerProjectionHealthTransitionResponseReason.HEALTH_DETERIORATING
HEALTH_ESCALATED = ResearchWorkspaceConsumerProjectionHealthTransitionResponseReason.HEALTH_ESCALATED


class TestPackageBuilding:
    """Test basic package construction from aligned artifacts."""

    def test_valid_directive_and_rationale_produce_a_package(self):
        directive = _make_directive(recommendation=INVESTIGATE, priority=HIGH)
        rationale = _make_rationale(
            reason=HEALTH_DETERIORATING,
            recommendation=INVESTIGATE,
            priority=HIGH,
            summary="Execution health is deteriorating.",
        )

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePackageBuilder()
        package = builder.build(directive, rationale)

        assert package.recommendation == INVESTIGATE
        assert package.priority == HIGH
        assert package.reason == HEALTH_DETERIORATING

    def test_projection_name_is_preserved(self):
        directive = _make_directive(projection_name="workspace.attention")
        rationale = _make_rationale(projection_name="workspace.attention")

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePackageBuilder()
        package = builder.build(directive, rationale)

        assert package.projection_name == "workspace.attention"

    def test_previous_execution_id_is_preserved(self):
        directive = _make_directive(previous_execution_id="req-previous")
        rationale = _make_rationale(previous_execution_id="req-previous")

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePackageBuilder()
        package = builder.build(directive, rationale)

        assert package.previous_execution_id == "req-previous"

    def test_current_execution_id_is_preserved(self):
        directive = _make_directive(current_execution_id="req-current")
        rationale = _make_rationale(current_execution_id="req-current")

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePackageBuilder()
        package = builder.build(directive, rationale)

        assert package.current_execution_id == "req-current"

    def test_recommendation_is_preserved(self):
        directive = _make_directive(recommendation=PRIORITIZE_REVIEW, priority=URGENT)
        rationale = _make_rationale(
            reason=HEALTH_ESCALATED,
            recommendation=PRIORITIZE_REVIEW,
            priority=URGENT,
        )

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePackageBuilder()
        package = builder.build(directive, rationale)

        assert package.recommendation == PRIORITIZE_REVIEW

    def test_priority_is_preserved(self):
        directive = _make_directive(recommendation=PRIORITIZE_REVIEW, priority=URGENT)
        rationale = _make_rationale(
            reason=HEALTH_ESCALATED,
            recommendation=PRIORITIZE_REVIEW,
            priority=URGENT,
        )

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePackageBuilder()
        package = builder.build(directive, rationale)

        assert package.priority == URGENT

    def test_reason_is_preserved(self):
        directive = _make_directive(recommendation=INVESTIGATE, priority=HIGH)
        rationale = _make_rationale(
            reason=HEALTH_DETERIORATING,
            recommendation=INVESTIGATE,
            priority=HIGH,
        )

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePackageBuilder()
        package = builder.build(directive, rationale)

        assert package.reason == HEALTH_DETERIORATING

    def test_summary_is_preserved(self):
        directive = _make_directive(recommendation=INVESTIGATE, priority=HIGH)
        rationale = _make_rationale(
            reason=HEALTH_DETERIORATING,
            recommendation=INVESTIGATE,
            priority=HIGH,
            summary="Execution health is deteriorating.",
        )

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePackageBuilder()
        package = builder.build(directive, rationale)

        assert package.summary == "Execution health is deteriorating."

    def test_action_recommended_is_preserved(self):
        directive = _make_directive(recommendation=PRIORITIZE_REVIEW, priority=URGENT)
        rationale = _make_rationale(
            reason=HEALTH_ESCALATED,
            recommendation=PRIORITIZE_REVIEW,
            priority=URGENT,
        )

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePackageBuilder()
        package = builder.build(directive, rationale)

        assert package.action_recommended == directive.action_recommended
        assert package.action_recommended is True


class TestValidation:
    """Test rejection of misaligned or inconsistent artifacts."""

    def test_projection_mismatch_raises_error(self):
        directive = _make_directive(projection_name="workspace.bootstrap")
        rationale = _make_rationale(projection_name="workspace.attention")

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePackageBuilder()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionHealthTransitionResponsePackageError
        ):
            builder.build(directive, rationale)

    def test_previous_execution_id_mismatch_raises_error(self):
        directive = _make_directive(previous_execution_id="exec-a")
        rationale = _make_rationale(previous_execution_id="exec-b")

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePackageBuilder()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionHealthTransitionResponsePackageError
        ):
            builder.build(directive, rationale)

    def test_current_execution_id_mismatch_raises_error(self):
        directive = _make_directive(current_execution_id="exec-a")
        rationale = _make_rationale(current_execution_id="exec-b")

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePackageBuilder()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionHealthTransitionResponsePackageError
        ):
            builder.build(directive, rationale)

    def test_recommendation_mismatch_raises_error(self):
        directive = _make_directive(recommendation=INVESTIGATE, priority=HIGH)
        rationale = _make_rationale(
            recommendation=NO_ACTION, priority=NONE_PRIORITY
        )

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePackageBuilder()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionHealthTransitionResponsePackageError
        ):
            builder.build(directive, rationale)

    def test_priority_mismatch_raises_error(self):
        directive = _make_directive(recommendation=INVESTIGATE, priority=HIGH)
        rationale = _make_rationale(recommendation=INVESTIGATE, priority=URGENT)

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePackageBuilder()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionHealthTransitionResponsePackageError
        ):
            builder.build(directive, rationale)

    def test_builder_does_not_repair_inconsistent_artifacts(self):
        # An inconsistent pair must raise, never silently coerce one
        # artifact's values to match the other's.
        directive = _make_directive(recommendation=PRIORITIZE_REVIEW, priority=URGENT)
        rationale = _make_rationale(
            reason=HEALTH_STABLE, recommendation=NO_ACTION, priority=NONE_PRIORITY
        )

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePackageBuilder()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionHealthTransitionResponsePackageError
        ):
            builder.build(directive, rationale)


class TestDeterminism:
    """Test package building is deterministic."""

    def test_equivalent_inputs_produce_equivalent_packages(self):
        directive = _make_directive(recommendation=INVESTIGATE, priority=HIGH)
        rationale = _make_rationale(
            reason=HEALTH_DETERIORATING,
            recommendation=INVESTIGATE,
            priority=HIGH,
            summary="Execution health is deteriorating.",
        )

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePackageBuilder()

        package1 = builder.build(directive, rationale)
        package2 = builder.build(directive, rationale)

        assert package1 == package2


class TestArchitecturalBoundaries:
    """Test structural guarantees of the builder."""

    def test_builder_has_no_external_dependencies(self):
        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePackageBuilder()

        assert builder.__dict__ == {}

    def test_builder_does_not_mutate_inputs(self):
        directive = _make_directive(recommendation=INVESTIGATE, priority=HIGH)
        rationale = _make_rationale(
            reason=HEALTH_DETERIORATING,
            recommendation=INVESTIGATE,
            priority=HIGH,
        )

        directive_dict = directive.to_dict()
        rationale_dict = rationale.to_dict()

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePackageBuilder()
        builder.build(directive, rationale)

        assert directive.to_dict() == directive_dict
        assert rationale.to_dict() == rationale_dict

    def test_builder_works_from_artifacts_alone(self):
        # No receipt, quality signal, transition explanation, impact
        # summary, or assessment object is ever constructed here -
        # proves the builder only needs the directive and rationale.
        directive = _make_directive(
            previous_execution_id="artifacts-only-previous",
            current_execution_id="artifacts-only-current",
            recommendation=PRIORITIZE_REVIEW,
            priority=URGENT,
        )
        rationale = _make_rationale(
            previous_execution_id="artifacts-only-previous",
            current_execution_id="artifacts-only-current",
            reason=HEALTH_ESCALATED,
            recommendation=PRIORITIZE_REVIEW,
            priority=URGENT,
            summary="Execution health escalated to a critical state.",
        )

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePackageBuilder()
        package = builder.build(directive, rationale)

        assert package.reason == HEALTH_ESCALATED
        assert package.action_recommended is True


class TestResponsePlanner:
    """Test the end-to-end assessment-to-package composition planner."""

    def test_planner_delegates_to_existing_services(self):
        assessment = _make_assessment()

        fake_recommendation = object()
        fake_priority = object()
        fake_directive = object()
        fake_rationale = object()
        fake_package = object()

        recommendation_resolver = _RecordingRecommendationResolver(
            recommendation_to_return=fake_recommendation
        )
        priority_resolver = _RecordingPriorityResolver(
            priority_to_return=fake_priority
        )
        directive_builder = _RecordingDirectiveBuilder(
            directive_to_return=fake_directive
        )
        rationale_builder = _RecordingRationaleBuilder(
            rationale_to_return=fake_rationale
        )
        package_builder = _RecordingPackageBuilder(
            package_to_return=fake_package
        )

        planner = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanner(
            recommendation_resolver=recommendation_resolver,
            priority_resolver=priority_resolver,
            directive_builder=directive_builder,
            rationale_builder=rationale_builder,
            package_builder=package_builder,
        )

        result = planner.plan(assessment)

        assert recommendation_resolver.received_assessment is assessment
        assert priority_resolver.received_recommendation is fake_recommendation
        assert directive_builder.received_args == (
            fake_recommendation,
            fake_priority,
        )
        assert rationale_builder.received_args == (assessment, fake_directive)
        assert package_builder.received_args == (fake_directive, fake_rationale)
        assert result is fake_package

    def test_planner_does_not_duplicate_decision_logic(self):
        assessment = _make_assessment(
            assessment=ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind.ESCALATED
        )

        planner = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanner()
        actual = planner.plan(assessment)

        recommendation = planner._recommendation_resolver.resolve(assessment)
        priority = planner._priority_resolver.resolve(recommendation)
        directive = planner._directive_builder.build(recommendation, priority)
        rationale = planner._rationale_builder.build(assessment, directive)
        expected = planner._package_builder.build(directive, rationale)

        assert actual == expected

    def test_planner_uses_default_services_when_not_provided(self):
        assessment = _make_assessment(
            assessment=ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind.ESCALATED
        )

        planner = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanner()
        package = planner.plan(assessment)

        assert package.recommendation == PRIORITIZE_REVIEW
        assert package.priority == URGENT
        assert package.reason == HEALTH_ESCALATED
        assert package.action_recommended is True
