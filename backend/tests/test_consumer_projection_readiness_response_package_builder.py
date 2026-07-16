import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionReadinessDirective,
    ResearchWorkspaceConsumerProjectionReadinessPriority,
    ResearchWorkspaceConsumerProjectionReadinessRationale,
    ResearchWorkspaceConsumerProjectionReadinessReasonCode,
    ResearchWorkspaceConsumerProjectionReadinessRecommendation,
    ResearchWorkspaceConsumerProjectionReadinessResponsePackageBuilder,
    ResearchWorkspaceConsumerProjectionReadinessResponsePackageError,
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

READY_REASON = ResearchWorkspaceConsumerProjectionReadinessReasonCode.READY
DETERIORATING_REASON = (
    ResearchWorkspaceConsumerProjectionReadinessReasonCode.DETERIORATING
)
BLOCKED_REASON = (
    ResearchWorkspaceConsumerProjectionReadinessReasonCode.BLOCKED
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


def _make_rationale(
    *,
    projection_name="workspace.bootstrap",
    reason=READY_REASON,
    recommendation=NO_ACTION,
    priority=NONE_PRIORITY,
    summary="Projection is ready.",
):
    return ResearchWorkspaceConsumerProjectionReadinessRationale(
        projection_name=projection_name,
        reason=reason,
        recommendation=recommendation,
        priority=priority,
        summary=summary,
    )


class TestPackageBuilding:
    """A valid directive/rationale pair builds a response package."""

    def test_package_builds_correctly(self):
        directive = _make_directive(
            recommendation=UNBLOCK_EXECUTION, priority=CRITICAL
        )
        rationale = _make_rationale(
            reason=BLOCKED_REASON,
            recommendation=UNBLOCK_EXECUTION,
            priority=CRITICAL,
            summary="Projection execution is blocked.",
        )

        builder = (
            ResearchWorkspaceConsumerProjectionReadinessResponsePackageBuilder()
        )
        package = builder.build(directive, rationale)

        assert package.projection_name == "workspace.bootstrap"
        assert package.recommendation == UNBLOCK_EXECUTION
        assert package.priority == CRITICAL
        assert package.reason == BLOCKED_REASON
        assert package.summary == "Projection execution is blocked."
        assert package.action_required is True


class TestRecommendationPreserved:
    """recommendation is copied from the directive, not recomputed."""

    def test_recommendation_is_preserved(self):
        directive = _make_directive(
            recommendation=INVESTIGATE, priority=HIGH
        )
        rationale = _make_rationale(
            reason=DETERIORATING_REASON,
            recommendation=INVESTIGATE,
            priority=HIGH,
            summary="Projection readiness is deteriorating.",
        )

        builder = (
            ResearchWorkspaceConsumerProjectionReadinessResponsePackageBuilder()
        )
        package = builder.build(directive, rationale)

        assert package.recommendation == INVESTIGATE


class TestPriorityPreserved:
    """priority is copied from the directive, not recomputed."""

    def test_priority_is_preserved(self):
        directive = _make_directive(
            recommendation=INVESTIGATE, priority=HIGH
        )
        rationale = _make_rationale(
            reason=DETERIORATING_REASON,
            recommendation=INVESTIGATE,
            priority=HIGH,
            summary="Projection readiness is deteriorating.",
        )

        builder = (
            ResearchWorkspaceConsumerProjectionReadinessResponsePackageBuilder()
        )
        package = builder.build(directive, rationale)

        assert package.priority == HIGH


class TestReasonPreserved:
    """reason is copied from the rationale, not recomputed."""

    def test_reason_is_preserved(self):
        directive = _make_directive(
            recommendation=INVESTIGATE, priority=HIGH
        )
        rationale = _make_rationale(
            reason=DETERIORATING_REASON,
            recommendation=INVESTIGATE,
            priority=HIGH,
            summary="Projection readiness is deteriorating.",
        )

        builder = (
            ResearchWorkspaceConsumerProjectionReadinessResponsePackageBuilder()
        )
        package = builder.build(directive, rationale)

        assert package.reason == DETERIORATING_REASON


class TestSummaryPreserved:
    """summary is copied from the rationale, not recomputed."""

    def test_summary_is_preserved(self):
        directive = _make_directive(
            recommendation=INVESTIGATE, priority=HIGH
        )
        rationale = _make_rationale(
            reason=DETERIORATING_REASON,
            recommendation=INVESTIGATE,
            priority=HIGH,
            summary="Projection readiness is deteriorating.",
        )

        builder = (
            ResearchWorkspaceConsumerProjectionReadinessResponsePackageBuilder()
        )
        package = builder.build(directive, rationale)

        assert package.summary == "Projection readiness is deteriorating."


class TestActionRequiredPreserved:
    """action_required is copied from the directive, not recomputed."""

    def test_action_required_preserved_true(self):
        directive = _make_directive(
            recommendation=UNBLOCK_EXECUTION, priority=CRITICAL
        )
        rationale = _make_rationale(
            reason=BLOCKED_REASON,
            recommendation=UNBLOCK_EXECUTION,
            priority=CRITICAL,
            summary="Projection execution is blocked.",
        )

        builder = (
            ResearchWorkspaceConsumerProjectionReadinessResponsePackageBuilder()
        )
        package = builder.build(directive, rationale)

        assert package.action_required is True

    def test_action_required_preserved_false(self):
        directive = _make_directive(
            recommendation=NO_ACTION, priority=NONE_PRIORITY
        )
        rationale = _make_rationale(
            reason=READY_REASON,
            recommendation=NO_ACTION,
            priority=NONE_PRIORITY,
            summary="Projection is ready.",
        )

        builder = (
            ResearchWorkspaceConsumerProjectionReadinessResponsePackageBuilder()
        )
        package = builder.build(directive, rationale)

        assert package.action_required is False


class TestProjectionMismatch:
    """A directive/rationale pair for different projections is rejected."""

    def test_projection_mismatch_raises_error(self):
        directive = _make_directive(projection_name="workspace.bootstrap")
        rationale = _make_rationale(projection_name="workspace.attention")

        builder = (
            ResearchWorkspaceConsumerProjectionReadinessResponsePackageBuilder()
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionReadinessResponsePackageError
        ):
            builder.build(directive, rationale)


class TestRecommendationMismatch:
    """A rationale built from a different recommendation is rejected."""

    def test_recommendation_mismatch_raises_error(self):
        directive = _make_directive(
            recommendation=NO_ACTION, priority=NONE_PRIORITY
        )
        rationale = _make_rationale(
            reason=BLOCKED_REASON,
            recommendation=UNBLOCK_EXECUTION,
            priority=CRITICAL,
        )

        builder = (
            ResearchWorkspaceConsumerProjectionReadinessResponsePackageBuilder()
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionReadinessResponsePackageError
        ):
            builder.build(directive, rationale)


class TestPriorityMismatch:
    """A rationale carrying a different priority is rejected."""

    def test_priority_mismatch_raises_error(self):
        directive = _make_directive(
            recommendation=INVESTIGATE, priority=HIGH
        )
        rationale = _make_rationale(
            reason=DETERIORATING_REASON,
            recommendation=INVESTIGATE,
            priority=CRITICAL,
        )

        builder = (
            ResearchWorkspaceConsumerProjectionReadinessResponsePackageBuilder()
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionReadinessResponsePackageError
        ):
            builder.build(directive, rationale)


class TestDeterminism:
    """Building the same pair twice yields equal packages."""

    def test_equivalent_inputs_produce_equivalent_packages(self):
        directive = _make_directive(
            recommendation=INVESTIGATE, priority=HIGH
        )
        rationale = _make_rationale(
            reason=DETERIORATING_REASON,
            recommendation=INVESTIGATE,
            priority=HIGH,
            summary="Projection readiness is deteriorating.",
        )

        builder = (
            ResearchWorkspaceConsumerProjectionReadinessResponsePackageBuilder()
        )

        first = builder.build(directive, rationale)
        second = builder.build(directive, rationale)

        assert first == second


class TestArchitecturalBoundaries:
    """Structural guarantees: no state, no mutation, no side effects."""

    def test_builder_has_no_external_dependencies(self):
        builder = (
            ResearchWorkspaceConsumerProjectionReadinessResponsePackageBuilder()
        )

        assert builder.__dict__ == {}

    def test_builder_does_not_mutate_inputs(self):
        directive = _make_directive(
            recommendation=INVESTIGATE, priority=HIGH
        )
        rationale = _make_rationale(
            reason=DETERIORATING_REASON,
            recommendation=INVESTIGATE,
            priority=HIGH,
            summary="Projection readiness is deteriorating.",
        )

        directive_dict = directive.to_dict()
        rationale_dict = rationale.to_dict()

        builder = (
            ResearchWorkspaceConsumerProjectionReadinessResponsePackageBuilder()
        )
        builder.build(directive, rationale)

        assert directive.to_dict() == directive_dict
        assert rationale.to_dict() == rationale_dict

    def test_package_carries_no_persistence_or_workflow_state(self):
        directive = _make_directive()
        rationale = _make_rationale()

        builder = (
            ResearchWorkspaceConsumerProjectionReadinessResponsePackageBuilder()
        )
        package = builder.build(directive, rationale)

        assert set(package.to_dict().keys()) == {
            "projection_name",
            "recommendation",
            "priority",
            "reason",
            "summary",
            "action_required",
        }
