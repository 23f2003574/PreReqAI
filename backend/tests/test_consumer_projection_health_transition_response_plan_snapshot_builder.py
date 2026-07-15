import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionHealth,
    ResearchWorkspaceConsumerProjectionExecutionHealthTransition,
    ResearchWorkspaceConsumerProjectionHealthTransitionAssessment,
    ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind,
    ResearchWorkspaceConsumerProjectionHealthTransitionExplanation,
    ResearchWorkspaceConsumerProjectionHealthTransitionImpact,
    ResearchWorkspaceConsumerProjectionHealthTransitionImpactSummary,
    ResearchWorkspaceConsumerProjectionHealthTransitionKind,
    ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationKind,
    ResearchWorkspaceConsumerProjectionHealthTransitionResponsePackage,
    ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanSnapshotBuilder,
    ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanSnapshotError,
    ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanner,
    ResearchWorkspaceConsumerProjectionHealthTransitionResponsePriority,
    ResearchWorkspaceConsumerProjectionHealthTransitionResponseReason,
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


def _make_package(
    *,
    projection_name="workspace.bootstrap",
    previous_execution_id="exec-1",
    current_execution_id="exec-2",
    recommendation=ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationKind.NO_ACTION,
    priority=ResearchWorkspaceConsumerProjectionHealthTransitionResponsePriority.NONE,
    reason=ResearchWorkspaceConsumerProjectionHealthTransitionResponseReason.HEALTH_STABLE,
    summary="Execution health remained stable.",
    action_recommended=False,
):
    return ResearchWorkspaceConsumerProjectionHealthTransitionResponsePackage(
        projection_name=projection_name,
        previous_execution_id=previous_execution_id,
        current_execution_id=current_execution_id,
        recommendation=recommendation,
        priority=priority,
        reason=reason,
        summary=summary,
        action_recommended=action_recommended,
    )


def _make_explanation(
    *,
    projection_name="workspace.bootstrap",
    previous_execution_id="exec-1",
    current_execution_id="exec-2",
    transition=ResearchWorkspaceConsumerProjectionHealthTransitionKind.UNCHANGED,
    appeared_signals=(),
    resolved_signals=(),
    persistent_signals=(),
    severity_changes=(),
):
    return ResearchWorkspaceConsumerProjectionHealthTransitionExplanation(
        projection_name=projection_name,
        previous_execution_id=previous_execution_id,
        current_execution_id=current_execution_id,
        transition=transition,
        appeared_signals=tuple(appeared_signals),
        resolved_signals=tuple(resolved_signals),
        persistent_signals=tuple(persistent_signals),
        severity_changes=tuple(severity_changes),
    )


class _RecordingImpactSummarizer:
    def __init__(self, impact_to_return):
        self._impact_to_return = impact_to_return
        self.received_explanation = None

    def summarize(self, explanation):
        self.received_explanation = explanation
        return self._impact_to_return


class _RecordingAssessor:
    def __init__(self, assessment_to_return):
        self._assessment_to_return = assessment_to_return
        self.received_args = None

    def assess(self, transition, impact):
        self.received_args = (transition, impact)
        return self._assessment_to_return


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

    def resolve(self, recommendation):
        return self._priority_to_return


class _RecordingDirectiveBuilder:
    def __init__(self, directive_to_return):
        self._directive_to_return = directive_to_return

    def build(self, recommendation, priority):
        return self._directive_to_return


class _RecordingRationaleBuilder:
    def __init__(self, rationale_to_return):
        self._rationale_to_return = rationale_to_return

    def build(self, assessment, directive):
        return self._rationale_to_return


class _RecordingPackageBuilder:
    def __init__(self, package_to_return):
        self._package_to_return = package_to_return

    def build(self, directive, rationale):
        return self._package_to_return


class _RecordingSnapshotBuilder:
    def __init__(self, snapshot_to_return):
        self._snapshot_to_return = snapshot_to_return
        self.received_kwargs = None

    def build(self, *, transition, impact, assessment, response):
        self.received_kwargs = {
            "transition": transition,
            "impact": impact,
            "assessment": assessment,
            "response": response,
        }
        return self._snapshot_to_return


UNCHANGED = ResearchWorkspaceConsumerProjectionHealthTransitionKind.UNCHANGED
BECAME_CRITICAL = ResearchWorkspaceConsumerProjectionHealthTransitionKind.BECAME_CRITICAL

NONE_IMPACT = ResearchWorkspaceConsumerProjectionHealthTransitionImpact.NONE
NEGATIVE = ResearchWorkspaceConsumerProjectionHealthTransitionImpact.NEGATIVE

STABLE = ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind.STABLE
ESCALATED = ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind.ESCALATED

NO_ACTION = ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationKind.NO_ACTION
PRIORITIZE_REVIEW = ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationKind.PRIORITIZE_REVIEW

NONE_PRIORITY = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePriority.NONE
URGENT = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePriority.URGENT

HEALTH_STABLE = ResearchWorkspaceConsumerProjectionHealthTransitionResponseReason.HEALTH_STABLE
HEALTH_ESCALATED = ResearchWorkspaceConsumerProjectionHealthTransitionResponseReason.HEALTH_ESCALATED


class TestSnapshotBuilding:
    """Test basic snapshot construction from a fully aligned decision chain."""

    def test_valid_aligned_artifacts_produce_a_snapshot(self):
        transition = _make_transition(kind=UNCHANGED)
        impact = _make_impact_summary(transition=UNCHANGED, impact=NONE_IMPACT)
        assessment = _make_assessment(
            transition=UNCHANGED, impact=NONE_IMPACT, assessment=STABLE
        )
        response = _make_package(
            recommendation=NO_ACTION, priority=NONE_PRIORITY, reason=HEALTH_STABLE
        )

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanSnapshotBuilder()
        snapshot = builder.build(
            transition=transition,
            impact=impact,
            assessment=assessment,
            response=response,
        )

        assert snapshot.transition == UNCHANGED
        assert snapshot.impact == NONE_IMPACT
        assert snapshot.assessment == STABLE
        assert snapshot.recommendation == NO_ACTION

    def test_projection_name_is_preserved(self):
        transition = _make_transition(projection_name="workspace.attention")
        impact = _make_impact_summary(projection_name="workspace.attention")
        assessment = _make_assessment(projection_name="workspace.attention")
        response = _make_package(projection_name="workspace.attention")

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanSnapshotBuilder()
        snapshot = builder.build(
            transition=transition,
            impact=impact,
            assessment=assessment,
            response=response,
        )

        assert snapshot.projection_name == "workspace.attention"

    def test_previous_execution_id_is_preserved(self):
        transition = _make_transition(previous_execution_id="req-previous")
        impact = _make_impact_summary(previous_execution_id="req-previous")
        assessment = _make_assessment(previous_execution_id="req-previous")
        response = _make_package(previous_execution_id="req-previous")

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanSnapshotBuilder()
        snapshot = builder.build(
            transition=transition,
            impact=impact,
            assessment=assessment,
            response=response,
        )

        assert snapshot.previous_execution_id == "req-previous"

    def test_current_execution_id_is_preserved(self):
        transition = _make_transition(current_execution_id="req-current")
        impact = _make_impact_summary(current_execution_id="req-current")
        assessment = _make_assessment(current_execution_id="req-current")
        response = _make_package(current_execution_id="req-current")

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanSnapshotBuilder()
        snapshot = builder.build(
            transition=transition,
            impact=impact,
            assessment=assessment,
            response=response,
        )

        assert snapshot.current_execution_id == "req-current"

    def test_transition_kind_is_preserved(self):
        transition = _make_transition(kind=BECAME_CRITICAL)
        impact = _make_impact_summary(transition=BECAME_CRITICAL, impact=NEGATIVE)
        assessment = _make_assessment(
            transition=BECAME_CRITICAL, impact=NEGATIVE, assessment=ESCALATED
        )
        response = _make_package(
            recommendation=PRIORITIZE_REVIEW,
            priority=URGENT,
            reason=HEALTH_ESCALATED,
            summary="Execution health escalated to a critical state.",
            action_recommended=True,
        )

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanSnapshotBuilder()
        snapshot = builder.build(
            transition=transition,
            impact=impact,
            assessment=assessment,
            response=response,
        )

        assert snapshot.transition == BECAME_CRITICAL

    def test_impact_is_preserved(self):
        transition = _make_transition(kind=BECAME_CRITICAL)
        impact = _make_impact_summary(transition=BECAME_CRITICAL, impact=NEGATIVE)
        assessment = _make_assessment(
            transition=BECAME_CRITICAL, impact=NEGATIVE, assessment=ESCALATED
        )
        response = _make_package(
            recommendation=PRIORITIZE_REVIEW,
            priority=URGENT,
            reason=HEALTH_ESCALATED,
        )

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanSnapshotBuilder()
        snapshot = builder.build(
            transition=transition,
            impact=impact,
            assessment=assessment,
            response=response,
        )

        assert snapshot.impact == NEGATIVE

    def test_assessment_is_preserved(self):
        transition = _make_transition(kind=BECAME_CRITICAL)
        impact = _make_impact_summary(transition=BECAME_CRITICAL, impact=NEGATIVE)
        assessment = _make_assessment(
            transition=BECAME_CRITICAL, impact=NEGATIVE, assessment=ESCALATED
        )
        response = _make_package(
            recommendation=PRIORITIZE_REVIEW,
            priority=URGENT,
            reason=HEALTH_ESCALATED,
        )

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanSnapshotBuilder()
        snapshot = builder.build(
            transition=transition,
            impact=impact,
            assessment=assessment,
            response=response,
        )

        assert snapshot.assessment == ESCALATED

    def test_recommendation_is_preserved(self):
        transition = _make_transition(kind=BECAME_CRITICAL)
        impact = _make_impact_summary(transition=BECAME_CRITICAL, impact=NEGATIVE)
        assessment = _make_assessment(
            transition=BECAME_CRITICAL, impact=NEGATIVE, assessment=ESCALATED
        )
        response = _make_package(
            recommendation=PRIORITIZE_REVIEW,
            priority=URGENT,
            reason=HEALTH_ESCALATED,
        )

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanSnapshotBuilder()
        snapshot = builder.build(
            transition=transition,
            impact=impact,
            assessment=assessment,
            response=response,
        )

        assert snapshot.recommendation == PRIORITIZE_REVIEW

    def test_priority_is_preserved(self):
        transition = _make_transition(kind=BECAME_CRITICAL)
        impact = _make_impact_summary(transition=BECAME_CRITICAL, impact=NEGATIVE)
        assessment = _make_assessment(
            transition=BECAME_CRITICAL, impact=NEGATIVE, assessment=ESCALATED
        )
        response = _make_package(
            recommendation=PRIORITIZE_REVIEW,
            priority=URGENT,
            reason=HEALTH_ESCALATED,
        )

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanSnapshotBuilder()
        snapshot = builder.build(
            transition=transition,
            impact=impact,
            assessment=assessment,
            response=response,
        )

        assert snapshot.priority == URGENT

    def test_reason_is_preserved(self):
        transition = _make_transition(kind=BECAME_CRITICAL)
        impact = _make_impact_summary(transition=BECAME_CRITICAL, impact=NEGATIVE)
        assessment = _make_assessment(
            transition=BECAME_CRITICAL, impact=NEGATIVE, assessment=ESCALATED
        )
        response = _make_package(
            recommendation=PRIORITIZE_REVIEW,
            priority=URGENT,
            reason=HEALTH_ESCALATED,
        )

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanSnapshotBuilder()
        snapshot = builder.build(
            transition=transition,
            impact=impact,
            assessment=assessment,
            response=response,
        )

        assert snapshot.reason == HEALTH_ESCALATED

    def test_summary_is_preserved(self):
        transition = _make_transition(kind=BECAME_CRITICAL)
        impact = _make_impact_summary(transition=BECAME_CRITICAL, impact=NEGATIVE)
        assessment = _make_assessment(
            transition=BECAME_CRITICAL, impact=NEGATIVE, assessment=ESCALATED
        )
        response = _make_package(
            recommendation=PRIORITIZE_REVIEW,
            priority=URGENT,
            reason=HEALTH_ESCALATED,
            summary="Execution health escalated to a critical state.",
        )

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanSnapshotBuilder()
        snapshot = builder.build(
            transition=transition,
            impact=impact,
            assessment=assessment,
            response=response,
        )

        assert snapshot.summary == "Execution health escalated to a critical state."

    def test_action_recommended_is_preserved(self):
        transition = _make_transition(kind=BECAME_CRITICAL)
        impact = _make_impact_summary(transition=BECAME_CRITICAL, impact=NEGATIVE)
        assessment = _make_assessment(
            transition=BECAME_CRITICAL, impact=NEGATIVE, assessment=ESCALATED
        )
        response = _make_package(
            recommendation=PRIORITIZE_REVIEW,
            priority=URGENT,
            reason=HEALTH_ESCALATED,
            action_recommended=True,
        )

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanSnapshotBuilder()
        snapshot = builder.build(
            transition=transition,
            impact=impact,
            assessment=assessment,
            response=response,
        )

        assert snapshot.action_recommended is True


class TestValidation:
    """Test rejection of misaligned or inconsistent decision chains."""

    def test_projection_mismatch_raises_error(self):
        transition = _make_transition(projection_name="workspace.bootstrap")
        impact = _make_impact_summary(projection_name="workspace.attention")
        assessment = _make_assessment(projection_name="workspace.bootstrap")
        response = _make_package(projection_name="workspace.bootstrap")

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanSnapshotBuilder()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanSnapshotError
        ):
            builder.build(
                transition=transition,
                impact=impact,
                assessment=assessment,
                response=response,
            )

    def test_previous_execution_id_mismatch_raises_error(self):
        transition = _make_transition(previous_execution_id="exec-a")
        impact = _make_impact_summary(previous_execution_id="exec-b")
        assessment = _make_assessment(previous_execution_id="exec-a")
        response = _make_package(previous_execution_id="exec-a")

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanSnapshotBuilder()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanSnapshotError
        ):
            builder.build(
                transition=transition,
                impact=impact,
                assessment=assessment,
                response=response,
            )

    def test_current_execution_id_mismatch_raises_error(self):
        transition = _make_transition(current_execution_id="exec-a")
        impact = _make_impact_summary(current_execution_id="exec-b")
        assessment = _make_assessment(current_execution_id="exec-a")
        response = _make_package(current_execution_id="exec-a")

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanSnapshotBuilder()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanSnapshotError
        ):
            builder.build(
                transition=transition,
                impact=impact,
                assessment=assessment,
                response=response,
            )

    def test_transition_mismatch_raises_error(self):
        # impact/assessment describe UNCHANGED while transition itself
        # is BECAME_CRITICAL.
        transition = _make_transition(kind=BECAME_CRITICAL)
        impact = _make_impact_summary(transition=UNCHANGED, impact=NONE_IMPACT)
        assessment = _make_assessment(
            transition=UNCHANGED, impact=NONE_IMPACT, assessment=STABLE
        )
        response = _make_package(recommendation=NO_ACTION, priority=NONE_PRIORITY)

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanSnapshotBuilder()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanSnapshotError
        ):
            builder.build(
                transition=transition,
                impact=impact,
                assessment=assessment,
                response=response,
            )

    def test_impact_mismatch_raises_error(self):
        # assessment claims NEGATIVE impact while impact summary says NONE.
        transition = _make_transition(kind=UNCHANGED)
        impact = _make_impact_summary(transition=UNCHANGED, impact=NONE_IMPACT)
        assessment = _make_assessment(
            transition=UNCHANGED, impact=NEGATIVE, assessment=STABLE
        )
        response = _make_package(recommendation=NO_ACTION, priority=NONE_PRIORITY)

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanSnapshotBuilder()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanSnapshotError
        ):
            builder.build(
                transition=transition,
                impact=impact,
                assessment=assessment,
                response=response,
            )

    def test_builder_does_not_repair_inconsistent_artifacts(self):
        # response package (PRIORITIZE_REVIEW/URGENT) is incompatible
        # with a STABLE assessment - must raise, never silently coerce.
        transition = _make_transition(kind=UNCHANGED)
        impact = _make_impact_summary(transition=UNCHANGED, impact=NONE_IMPACT)
        assessment = _make_assessment(
            transition=UNCHANGED, impact=NONE_IMPACT, assessment=STABLE
        )
        response = _make_package(
            recommendation=PRIORITIZE_REVIEW,
            priority=URGENT,
            reason=HEALTH_ESCALATED,
        )

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanSnapshotBuilder()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanSnapshotError
        ):
            builder.build(
                transition=transition,
                impact=impact,
                assessment=assessment,
                response=response,
            )


class TestDeterminism:
    """Test snapshot building is deterministic."""

    def test_equivalent_inputs_produce_equivalent_snapshots(self):
        transition = _make_transition(kind=UNCHANGED)
        impact = _make_impact_summary(transition=UNCHANGED, impact=NONE_IMPACT)
        assessment = _make_assessment(
            transition=UNCHANGED, impact=NONE_IMPACT, assessment=STABLE
        )
        response = _make_package(recommendation=NO_ACTION, priority=NONE_PRIORITY)

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanSnapshotBuilder()

        snapshot1 = builder.build(
            transition=transition,
            impact=impact,
            assessment=assessment,
            response=response,
        )
        snapshot2 = builder.build(
            transition=transition,
            impact=impact,
            assessment=assessment,
            response=response,
        )

        assert snapshot1 == snapshot2


class TestArchitecturalBoundaries:
    """Test structural guarantees of the builder."""

    def test_builder_has_no_external_dependencies(self):
        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanSnapshotBuilder()

        assert builder.__dict__ == {}

    def test_builder_does_not_mutate_inputs(self):
        transition = _make_transition(kind=UNCHANGED)
        impact = _make_impact_summary(transition=UNCHANGED, impact=NONE_IMPACT)
        assessment = _make_assessment(
            transition=UNCHANGED, impact=NONE_IMPACT, assessment=STABLE
        )
        response = _make_package(recommendation=NO_ACTION, priority=NONE_PRIORITY)

        transition_dict = transition.to_dict()
        impact_dict = impact.to_dict()
        assessment_dict = assessment.to_dict()
        response_dict = response.to_dict()

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanSnapshotBuilder()
        builder.build(
            transition=transition,
            impact=impact,
            assessment=assessment,
            response=response,
        )

        assert transition.to_dict() == transition_dict
        assert impact.to_dict() == impact_dict
        assert assessment.to_dict() == assessment_dict
        assert response.to_dict() == response_dict

    def test_builder_works_from_artifacts_alone(self):
        # No execution receipt, quality signal report, or transition
        # explanation object is ever constructed here - proves the
        # builder only needs the four decision-chain artifacts.
        transition = _make_transition(
            previous_execution_id="artifacts-only-previous",
            current_execution_id="artifacts-only-current",
            kind=UNCHANGED,
        )
        impact = _make_impact_summary(
            previous_execution_id="artifacts-only-previous",
            current_execution_id="artifacts-only-current",
            transition=UNCHANGED,
            impact=NONE_IMPACT,
        )
        assessment = _make_assessment(
            previous_execution_id="artifacts-only-previous",
            current_execution_id="artifacts-only-current",
            transition=UNCHANGED,
            impact=NONE_IMPACT,
            assessment=STABLE,
        )
        response = _make_package(
            previous_execution_id="artifacts-only-previous",
            current_execution_id="artifacts-only-current",
            recommendation=NO_ACTION,
            priority=NONE_PRIORITY,
        )

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanSnapshotBuilder()
        snapshot = builder.build(
            transition=transition,
            impact=impact,
            assessment=assessment,
            response=response,
        )

        assert snapshot.previous_execution_id == "artifacts-only-previous"
        assert snapshot.assessment == STABLE


class TestResponsePlannerSnapshot:
    """Test the end-to-end transition+explanation-to-snapshot planner method."""

    def test_planner_delegates_to_existing_services(self):
        transition = _make_transition(kind=UNCHANGED)
        explanation = _make_explanation(transition=UNCHANGED)

        fake_impact = object()
        fake_assessment = object()
        fake_recommendation = object()
        fake_priority = object()
        fake_directive = object()
        fake_rationale = object()
        fake_package = object()
        fake_snapshot = object()

        impact_summarizer = _RecordingImpactSummarizer(
            impact_to_return=fake_impact
        )
        assessor = _RecordingAssessor(assessment_to_return=fake_assessment)
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
        snapshot_builder = _RecordingSnapshotBuilder(
            snapshot_to_return=fake_snapshot
        )

        planner = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanner(
            impact_summarizer=impact_summarizer,
            assessor=assessor,
            recommendation_resolver=recommendation_resolver,
            priority_resolver=priority_resolver,
            directive_builder=directive_builder,
            rationale_builder=rationale_builder,
            package_builder=package_builder,
            snapshot_builder=snapshot_builder,
        )

        result = planner.build_snapshot(
            transition=transition, explanation=explanation
        )

        assert impact_summarizer.received_explanation is explanation
        assert assessor.received_args == (transition, fake_impact)
        assert recommendation_resolver.received_assessment is fake_assessment
        assert snapshot_builder.received_kwargs == {
            "transition": transition,
            "impact": fake_impact,
            "assessment": fake_assessment,
            "response": fake_package,
        }
        assert result is fake_snapshot

    def test_planner_does_not_duplicate_decision_logic(self):
        transition = _make_transition(kind=UNCHANGED)
        explanation = _make_explanation(transition=UNCHANGED)

        planner = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanner()
        actual = planner.build_snapshot(
            transition=transition, explanation=explanation
        )

        impact = planner._impact_summarizer.summarize(explanation)
        assessment = planner._assessor.assess(transition, impact)
        recommendation = planner._recommendation_resolver.resolve(assessment)
        priority = planner._priority_resolver.resolve(recommendation)
        directive = planner._directive_builder.build(recommendation, priority)
        rationale = planner._rationale_builder.build(assessment, directive)
        response = planner._package_builder.build(directive, rationale)
        expected = planner._snapshot_builder.build(
            transition=transition,
            impact=impact,
            assessment=assessment,
            response=response,
        )

        assert actual == expected

    def test_planner_uses_default_services_when_not_provided(self):
        transition = _make_transition(kind=UNCHANGED)
        explanation = _make_explanation(transition=UNCHANGED)

        planner = ResearchWorkspaceConsumerProjectionHealthTransitionResponsePlanner()
        snapshot = planner.build_snapshot(
            transition=transition, explanation=explanation
        )

        assert snapshot.transition == UNCHANGED
        assert snapshot.impact == NONE_IMPACT
        assert snapshot.assessment == STABLE
        assert snapshot.recommendation == NO_ACTION
        assert snapshot.reason == HEALTH_STABLE
        assert snapshot.action_recommended is False
