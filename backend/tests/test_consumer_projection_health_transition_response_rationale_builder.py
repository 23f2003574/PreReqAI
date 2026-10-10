import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionHealthTransitionAssessment,
    ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind,
    ResearchWorkspaceConsumerProjectionHealthTransitionImpact,
    ResearchWorkspaceConsumerProjectionHealthTransitionKind,
    ResearchWorkspaceConsumerProjectionHealthTransitionRecommendationKind,
    ResearchWorkspaceConsumerProjectionHealthTransitionResponseDirective,
    ResearchWorkspaceConsumerProjectionHealthTransitionResponsePriority,
    ResearchWorkspaceConsumerProjectionHealthTransitionResponseRationaleBuilder,
    ResearchWorkspaceConsumerProjectionHealthTransitionResponseRationaleError,
    ResearchWorkspaceConsumerProjectionHealthTransitionResponseReason,
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


STABLE = ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind.STABLE
IMPROVING = ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind.IMPROVING
RECOVERED = ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind.RECOVERED
MIXED = ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind.MIXED
DETERIORATING = ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind.DETERIORATING
ESCALATED = ResearchWorkspaceConsumerProjectionHealthTransitionAssessmentKind.ESCALATED

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

HEALTH_STABLE = ResearchWorkspaceConsumerProjectionHealthTransitionResponseReason.HEALTH_STABLE
CONDITIONS_IMPROVING = ResearchWorkspaceConsumerProjectionHealthTransitionResponseReason.CONDITIONS_IMPROVING
HEALTH_RECOVERED = ResearchWorkspaceConsumerProjectionHealthTransitionResponseReason.HEALTH_RECOVERED
MIXED_CHANGES = ResearchWorkspaceConsumerProjectionHealthTransitionResponseReason.MIXED_CHANGES
HEALTH_DETERIORATING = ResearchWorkspaceConsumerProjectionHealthTransitionResponseReason.HEALTH_DETERIORATING
HEALTH_ESCALATED = ResearchWorkspaceConsumerProjectionHealthTransitionResponseReason.HEALTH_ESCALATED

# Valid (assessment, recommendation, priority) triples, matching
# Commit #8/#9's established mappings.
_VALID_TRIPLES = [
    (STABLE, NO_ACTION, NONE_PRIORITY),
    (IMPROVING, CONTINUE_OBSERVATION, LOW),
    (RECOVERED, NO_ACTION, NONE_PRIORITY),
    (MIXED, REVIEW_CHANGES, MEDIUM),
    (DETERIORATING, INVESTIGATE, HIGH),
    (ESCALATED, PRIORITIZE_REVIEW, URGENT),
]


class TestReasonMapping:
    """Test the deterministic assessment-to-reason mapping."""

    @pytest.mark.parametrize(
        "assessment_kind,recommendation_kind,priority_kind,expected_reason",
        [
            (STABLE, NO_ACTION, NONE_PRIORITY, HEALTH_STABLE),
            (IMPROVING, CONTINUE_OBSERVATION, LOW, CONDITIONS_IMPROVING),
            (RECOVERED, NO_ACTION, NONE_PRIORITY, HEALTH_RECOVERED),
            (MIXED, REVIEW_CHANGES, MEDIUM, MIXED_CHANGES),
            (DETERIORATING, INVESTIGATE, HIGH, HEALTH_DETERIORATING),
            (ESCALATED, PRIORITIZE_REVIEW, URGENT, HEALTH_ESCALATED),
        ],
    )
    def test_reason_mapping(
        self,
        assessment_kind,
        recommendation_kind,
        priority_kind,
        expected_reason,
    ):
        assessment = _make_assessment(assessment=assessment_kind)
        directive = _make_directive(
            recommendation=recommendation_kind, priority=priority_kind
        )

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponseRationaleBuilder()
        rationale = builder.build(assessment, directive)

        assert rationale.reason == expected_reason


class TestSummaryText:
    """Test each reason produces fixed, deterministic summary text."""

    @pytest.mark.parametrize(
        "assessment_kind,recommendation_kind,priority_kind,expected_summary",
        [
            (STABLE, NO_ACTION, NONE_PRIORITY, "Execution health remained stable."),
            (
                IMPROVING,
                CONTINUE_OBSERVATION,
                LOW,
                "Execution conditions are improving.",
            ),
            (RECOVERED, NO_ACTION, NONE_PRIORITY, "Execution health recovered."),
            (
                MIXED,
                REVIEW_CHANGES,
                MEDIUM,
                "Execution changes have mixed impact.",
            ),
            (
                DETERIORATING,
                INVESTIGATE,
                HIGH,
                "Execution health is deteriorating.",
            ),
            (
                ESCALATED,
                PRIORITIZE_REVIEW,
                URGENT,
                "Execution health escalated to a critical state.",
            ),
        ],
    )
    def test_summary_text(
        self,
        assessment_kind,
        recommendation_kind,
        priority_kind,
        expected_summary,
    ):
        assessment = _make_assessment(assessment=assessment_kind)
        directive = _make_directive(
            recommendation=recommendation_kind, priority=priority_kind
        )

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponseRationaleBuilder()
        rationale = builder.build(assessment, directive)

        assert rationale.summary == expected_summary


class TestPreservation:
    """Test directive decisions and identity are reused, not regenerated."""

    def test_recommendation_is_preserved(self):
        assessment = _make_assessment(assessment=DETERIORATING)
        directive = _make_directive(recommendation=INVESTIGATE, priority=HIGH)

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponseRationaleBuilder()
        rationale = builder.build(assessment, directive)

        assert rationale.recommendation == INVESTIGATE

    def test_priority_is_preserved(self):
        assessment = _make_assessment(assessment=ESCALATED)
        directive = _make_directive(
            recommendation=PRIORITIZE_REVIEW, priority=URGENT
        )

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponseRationaleBuilder()
        rationale = builder.build(assessment, directive)

        assert rationale.priority == URGENT

    def test_projection_name_is_preserved(self):
        assessment = _make_assessment(projection_name="workspace.attention")
        directive = _make_directive(projection_name="workspace.attention")

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponseRationaleBuilder()
        rationale = builder.build(assessment, directive)

        assert rationale.projection_name == "workspace.attention"

    def test_execution_ids_are_preserved(self):
        assessment = _make_assessment(
            previous_execution_id="req-previous",
            current_execution_id="req-current",
        )
        directive = _make_directive(
            previous_execution_id="req-previous",
            current_execution_id="req-current",
        )

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponseRationaleBuilder()
        rationale = builder.build(assessment, directive)

        assert rationale.previous_execution_id == "req-previous"
        assert rationale.current_execution_id == "req-current"


class TestValidation:
    """Test rejection of misaligned or incompatible artifacts."""

    def test_projection_mismatch_raises_error(self):
        assessment = _make_assessment(projection_name="workspace.bootstrap")
        directive = _make_directive(projection_name="workspace.attention")

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponseRationaleBuilder()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionHealthTransitionResponseRationaleError
        ):
            builder.build(assessment, directive)

    def test_previous_execution_id_mismatch_raises_error(self):
        assessment = _make_assessment(previous_execution_id="exec-a")
        directive = _make_directive(previous_execution_id="exec-b")

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponseRationaleBuilder()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionHealthTransitionResponseRationaleError
        ):
            builder.build(assessment, directive)

    def test_current_execution_id_mismatch_raises_error(self):
        assessment = _make_assessment(current_execution_id="exec-a")
        directive = _make_directive(current_execution_id="exec-b")

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponseRationaleBuilder()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionHealthTransitionResponseRationaleError
        ):
            builder.build(assessment, directive)

    def test_incompatible_recommendation_raises_error(self):
        # DETERIORATING should be paired with INVESTIGATE/HIGH, not NO_ACTION/NONE.
        assessment = _make_assessment(assessment=DETERIORATING)
        directive = _make_directive(
            recommendation=NO_ACTION, priority=NONE_PRIORITY
        )

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponseRationaleBuilder()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionHealthTransitionResponseRationaleError
        ):
            builder.build(assessment, directive)

    def test_incompatible_priority_raises_error(self):
        # INVESTIGATE should be paired with HIGH, not an unrelated priority.
        assessment = _make_assessment(assessment=DETERIORATING)
        directive = _make_directive(
            recommendation=INVESTIGATE, priority=URGENT
        )

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponseRationaleBuilder()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionHealthTransitionResponseRationaleError
        ):
            builder.build(assessment, directive)


class TestDeterminism:
    """Test rationale building is deterministic."""

    def test_equivalent_inputs_produce_equivalent_rationales(self):
        assessment = _make_assessment(assessment=MIXED)
        directive = _make_directive(recommendation=REVIEW_CHANGES, priority=MEDIUM)

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponseRationaleBuilder()

        rationale1 = builder.build(assessment, directive)
        rationale2 = builder.build(assessment, directive)

        assert rationale1 == rationale2


class TestArchitecturalBoundaries:
    """Test structural guarantees of the builder."""

    def test_builder_has_no_external_dependencies(self):
        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponseRationaleBuilder()

        assert builder.__dict__ == {}

    def test_builder_does_not_mutate_inputs(self):
        assessment = _make_assessment(assessment=ESCALATED)
        directive = _make_directive(
            recommendation=PRIORITIZE_REVIEW, priority=URGENT
        )

        assessment_dict = assessment.to_dict()
        directive_dict = directive.to_dict()

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponseRationaleBuilder()
        builder.build(assessment, directive)

        assert assessment.to_dict() == assessment_dict
        assert directive.to_dict() == directive_dict

    def test_builder_works_from_artifacts_alone(self):
        # No receipt, quality signal, transition explanation, or
        # impact summary object is ever constructed here - proves the
        # builder only needs the assessment and directive.
        assessment = _make_assessment(
            previous_execution_id="artifacts-only-previous",
            current_execution_id="artifacts-only-current",
            assessment=RECOVERED,
        )
        directive = _make_directive(
            previous_execution_id="artifacts-only-previous",
            current_execution_id="artifacts-only-current",
            recommendation=NO_ACTION,
            priority=NONE_PRIORITY,
        )

        builder = ResearchWorkspaceConsumerProjectionHealthTransitionResponseRationaleBuilder()
        rationale = builder.build(assessment, directive)

        assert rationale.reason == HEALTH_RECOVERED
        assert rationale.summary == "Execution health recovered."
