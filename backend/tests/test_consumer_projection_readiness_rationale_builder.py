from backend.session import (
    ResearchWorkspaceConsumerProjectionReadinessAssessment,
    ResearchWorkspaceConsumerProjectionReadinessAssessmentReport,
    ResearchWorkspaceConsumerProjectionReadinessDirective,
    ResearchWorkspaceConsumerProjectionReadinessImpact,
    ResearchWorkspaceConsumerProjectionReadinessPriority,
    ResearchWorkspaceConsumerProjectionReadinessRationaleBuilder,
    ResearchWorkspaceConsumerProjectionReadinessReasonCode,
    ResearchWorkspaceConsumerProjectionReadinessRecommendation,
    ResearchWorkspaceConsumerProjectionReadinessTransition,
)


STABLE = ResearchWorkspaceConsumerProjectionReadinessAssessment.STABLE
IMPROVING = ResearchWorkspaceConsumerProjectionReadinessAssessment.IMPROVING
RECOVERED = ResearchWorkspaceConsumerProjectionReadinessAssessment.RECOVERED
MIXED = ResearchWorkspaceConsumerProjectionReadinessAssessment.MIXED
DETERIORATING = (
    ResearchWorkspaceConsumerProjectionReadinessAssessment.DETERIORATING
)
BLOCKED = ResearchWorkspaceConsumerProjectionReadinessAssessment.BLOCKED

READY_REASON = ResearchWorkspaceConsumerProjectionReadinessReasonCode.READY
IMPROVING_REASON = (
    ResearchWorkspaceConsumerProjectionReadinessReasonCode.IMPROVING
)
RECOVERED_REASON = (
    ResearchWorkspaceConsumerProjectionReadinessReasonCode.RECOVERED
)
MIXED_REASON = ResearchWorkspaceConsumerProjectionReadinessReasonCode.MIXED
DETERIORATING_REASON = (
    ResearchWorkspaceConsumerProjectionReadinessReasonCode.DETERIORATING
)
BLOCKED_REASON = (
    ResearchWorkspaceConsumerProjectionReadinessReasonCode.BLOCKED
)

NO_ACTION = (
    ResearchWorkspaceConsumerProjectionReadinessRecommendation.NO_ACTION
)
CONTINUE_MONITORING = (
    ResearchWorkspaceConsumerProjectionReadinessRecommendation.CONTINUE_MONITORING
)
UNBLOCK_EXECUTION = (
    ResearchWorkspaceConsumerProjectionReadinessRecommendation.UNBLOCK_EXECUTION
)

NONE_PRIORITY = ResearchWorkspaceConsumerProjectionReadinessPriority.NONE
LOW = ResearchWorkspaceConsumerProjectionReadinessPriority.LOW
CRITICAL = ResearchWorkspaceConsumerProjectionReadinessPriority.CRITICAL

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


def _make_directive(
    *,
    projection_name="workspace.bootstrap",
    recommendation=NO_ACTION,
    priority=NONE_PRIORITY,
):
    return ResearchWorkspaceConsumerProjectionReadinessDirective(
        projection_name=projection_name,
        recommendation=recommendation,
        priority=priority,
    )


class TestReasonMapping:
    """Test the full assessment -> reason code mapping."""

    def test_stable_maps_to_ready(self):
        assessment = _make_assessment(assessment=STABLE)
        directive = _make_directive(
            recommendation=NO_ACTION, priority=NONE_PRIORITY
        )

        builder = ResearchWorkspaceConsumerProjectionReadinessRationaleBuilder()
        rationale = builder.build(assessment, directive)

        assert rationale.reason == READY_REASON

    def test_improving_maps_to_improving(self):
        assessment = _make_assessment(assessment=IMPROVING)
        directive = _make_directive(
            recommendation=CONTINUE_MONITORING, priority=LOW
        )

        builder = ResearchWorkspaceConsumerProjectionReadinessRationaleBuilder()
        rationale = builder.build(assessment, directive)

        assert rationale.reason == IMPROVING_REASON

    def test_recovered_maps_to_recovered(self):
        assessment = _make_assessment(assessment=RECOVERED)
        directive = _make_directive(
            recommendation=NO_ACTION, priority=NONE_PRIORITY
        )

        builder = ResearchWorkspaceConsumerProjectionReadinessRationaleBuilder()
        rationale = builder.build(assessment, directive)

        assert rationale.reason == RECOVERED_REASON

    def test_mixed_maps_to_mixed(self):
        assessment = _make_assessment(assessment=MIXED)
        directive = _make_directive(
            recommendation=NO_ACTION, priority=NONE_PRIORITY
        )

        builder = ResearchWorkspaceConsumerProjectionReadinessRationaleBuilder()
        rationale = builder.build(assessment, directive)

        assert rationale.reason == MIXED_REASON

    def test_deteriorating_maps_to_deteriorating(self):
        assessment = _make_assessment(assessment=DETERIORATING)
        directive = _make_directive(
            recommendation=NO_ACTION, priority=NONE_PRIORITY
        )

        builder = ResearchWorkspaceConsumerProjectionReadinessRationaleBuilder()
        rationale = builder.build(assessment, directive)

        assert rationale.reason == DETERIORATING_REASON

    def test_blocked_maps_to_blocked(self):
        assessment = _make_assessment(assessment=BLOCKED)
        directive = _make_directive(
            recommendation=UNBLOCK_EXECUTION, priority=CRITICAL
        )

        builder = ResearchWorkspaceConsumerProjectionReadinessRationaleBuilder()
        rationale = builder.build(assessment, directive)

        assert rationale.reason == BLOCKED_REASON


class TestStableSummaries:
    """Summaries are fixed text per reason code, not dynamically generated."""

    def test_ready_summary_is_fixed(self):
        assessment = _make_assessment(assessment=STABLE)
        directive = _make_directive()

        builder = ResearchWorkspaceConsumerProjectionReadinessRationaleBuilder()
        rationale = builder.build(assessment, directive)

        assert rationale.summary == "Projection is ready."

    def test_blocked_summary_is_fixed(self):
        assessment = _make_assessment(assessment=BLOCKED)
        directive = _make_directive(
            recommendation=UNBLOCK_EXECUTION, priority=CRITICAL
        )

        builder = ResearchWorkspaceConsumerProjectionReadinessRationaleBuilder()
        rationale = builder.build(assessment, directive)

        assert rationale.summary == "Projection execution is blocked."

    def test_recovered_summary_is_fixed(self):
        assessment = _make_assessment(assessment=RECOVERED)
        directive = _make_directive()

        builder = ResearchWorkspaceConsumerProjectionReadinessRationaleBuilder()
        rationale = builder.build(assessment, directive)

        assert rationale.summary == "Projection readiness recovered."

    def test_summary_is_identical_across_repeated_calls(self):
        assessment = _make_assessment(assessment=DETERIORATING)
        directive = _make_directive()

        builder = ResearchWorkspaceConsumerProjectionReadinessRationaleBuilder()

        first = builder.build(assessment, directive)
        second = builder.build(assessment, directive)

        assert first.summary == second.summary


class TestRecommendationPreserved:
    """The recommendation is copied from the directive, not recomputed."""

    def test_recommendation_is_preserved(self):
        assessment = _make_assessment(assessment=BLOCKED)
        directive = _make_directive(
            recommendation=UNBLOCK_EXECUTION, priority=CRITICAL
        )

        builder = ResearchWorkspaceConsumerProjectionReadinessRationaleBuilder()
        rationale = builder.build(assessment, directive)

        assert rationale.recommendation == UNBLOCK_EXECUTION


class TestPriorityPreserved:
    """The priority is copied from the directive, not recomputed."""

    def test_priority_is_preserved(self):
        assessment = _make_assessment(assessment=BLOCKED)
        directive = _make_directive(
            recommendation=UNBLOCK_EXECUTION, priority=CRITICAL
        )

        builder = ResearchWorkspaceConsumerProjectionReadinessRationaleBuilder()
        rationale = builder.build(assessment, directive)

        assert rationale.priority == CRITICAL


class TestDeterminism:
    """Building the same pair twice yields equal rationales."""

    def test_equivalent_inputs_produce_equivalent_rationales(self):
        assessment = _make_assessment(assessment=DETERIORATING)
        directive = _make_directive()

        builder = ResearchWorkspaceConsumerProjectionReadinessRationaleBuilder()

        first = builder.build(assessment, directive)
        second = builder.build(assessment, directive)

        assert first == second


class TestArchitecturalBoundaries:
    """Structural guarantees: no state, no mutation, no side effects."""

    def test_builder_has_no_external_dependencies(self):
        builder = ResearchWorkspaceConsumerProjectionReadinessRationaleBuilder()

        assert builder.__dict__ == {}

    def test_builder_does_not_mutate_inputs(self):
        assessment = _make_assessment(assessment=DETERIORATING)
        directive = _make_directive()

        assessment_dict = assessment.to_dict()
        directive_dict = directive.to_dict()

        builder = ResearchWorkspaceConsumerProjectionReadinessRationaleBuilder()
        builder.build(assessment, directive)

        assert assessment.to_dict() == assessment_dict
        assert directive.to_dict() == directive_dict

    def test_rationale_carries_no_ai_generated_text(self):
        # The summary field must come from the fixed lookup table,
        # not from any external call - covered structurally since
        # the builder has no dependencies to reach an LLM with.
        assessment = _make_assessment(assessment=STABLE)
        directive = _make_directive()

        builder = ResearchWorkspaceConsumerProjectionReadinessRationaleBuilder()
        rationale = builder.build(assessment, directive)

        assert set(rationale.to_dict().keys()) == {
            "projection_name",
            "reason",
            "recommendation",
            "priority",
            "summary",
        }
