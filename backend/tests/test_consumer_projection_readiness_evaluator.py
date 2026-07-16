from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionPlan,
    ResearchWorkspaceConsumerProjectionExecutionPlanDependency,
    ResearchWorkspaceConsumerProjectionExecutionPlanSource,
    ResearchWorkspaceConsumerProjectionExecutionPlanStage,
    ResearchWorkspaceConsumerProjectionReadiness,
    ResearchWorkspaceConsumerProjectionReadinessEvaluator,
    ResearchWorkspaceConsumerProjectionReadinessReason,
    ResearchWorkspaceConsumerProjectionStageRequirement,
)


MANDATORY = ResearchWorkspaceConsumerProjectionStageRequirement.MANDATORY
OPTIONAL = ResearchWorkspaceConsumerProjectionStageRequirement.OPTIONAL

READY = ResearchWorkspaceConsumerProjectionReadiness.READY
DEGRADED_READY = ResearchWorkspaceConsumerProjectionReadiness.DEGRADED_READY
BLOCKED = ResearchWorkspaceConsumerProjectionReadiness.BLOCKED

ALL_REQUIREMENTS_MET = (
    ResearchWorkspaceConsumerProjectionReadinessReason.ALL_REQUIREMENTS_MET
)
OPTIONAL_CONSTRAINTS_PRESENT = (
    ResearchWorkspaceConsumerProjectionReadinessReason.OPTIONAL_CONSTRAINTS_PRESENT
)
REQUIRED_DEPENDENCY_MISSING = (
    ResearchWorkspaceConsumerProjectionReadinessReason.REQUIRED_DEPENDENCY_MISSING
)
REQUIRED_SOURCE_UNAVAILABLE = (
    ResearchWorkspaceConsumerProjectionReadinessReason.REQUIRED_SOURCE_UNAVAILABLE
)
EXECUTION_DISABLED = (
    ResearchWorkspaceConsumerProjectionReadinessReason.EXECUTION_DISABLED
)
BUDGET_EXHAUSTED_REASON = (
    ResearchWorkspaceConsumerProjectionReadinessReason.BUDGET_EXHAUSTED
)


def _make_plan(
    *,
    projection_name="workspace.bootstrap",
    enabled=True,
    budget_available=True,
    required_dependencies=(),
    required_sources=(),
    stages=(),
):
    return ResearchWorkspaceConsumerProjectionExecutionPlan(
        projection_name=projection_name,
        enabled=enabled,
        budget_available=budget_available,
        required_dependencies=required_dependencies,
        required_sources=required_sources,
        stages=stages,
    )


class TestHealthyPlan:
    """A fully satisfied plan is READY with no issues."""

    def test_healthy_plan_is_ready(self):
        plan = _make_plan(
            required_dependencies=(
                ResearchWorkspaceConsumerProjectionExecutionPlanDependency(
                    name="cache",
                    satisfied=True,
                ),
            ),
            required_sources=(
                ResearchWorkspaceConsumerProjectionExecutionPlanSource(
                    name="arxiv",
                    expired=False,
                ),
            ),
            stages=(
                ResearchWorkspaceConsumerProjectionExecutionPlanStage(
                    name="fetch",
                    requirement=MANDATORY,
                    will_execute=True,
                ),
                ResearchWorkspaceConsumerProjectionExecutionPlanStage(
                    name="enrich",
                    requirement=OPTIONAL,
                    will_execute=True,
                ),
            ),
        )

        evaluator = ResearchWorkspaceConsumerProjectionReadinessEvaluator()
        report = evaluator.evaluate(plan)

        assert report.readiness == READY
        assert report.executable is True
        assert report.issues == ()
        assert report.reason == ALL_REQUIREMENTS_MET


class TestOptionalDegradation:
    """Degraded-but-executable inputs produce DEGRADED_READY."""

    def test_skipped_optional_stage_produces_degraded_ready(self):
        plan = _make_plan(
            stages=(
                ResearchWorkspaceConsumerProjectionExecutionPlanStage(
                    name="enrich",
                    requirement=OPTIONAL,
                    will_execute=False,
                ),
            ),
        )

        evaluator = ResearchWorkspaceConsumerProjectionReadinessEvaluator()
        report = evaluator.evaluate(plan)

        assert report.readiness == DEGRADED_READY
        assert report.executable is True
        assert len(report.issues) == 1
        assert report.issues[0].code == "optional_stage_skipped"
        assert (
            report.issues[0].message
            == "optional stage 'enrich' will be skipped"
        )
        assert report.reason == OPTIONAL_CONSTRAINTS_PRESENT

    def test_degraded_dependency_produces_degraded_ready(self):
        plan = _make_plan(
            required_dependencies=(
                ResearchWorkspaceConsumerProjectionExecutionPlanDependency(
                    name="cache",
                    satisfied=True,
                    degraded=True,
                ),
            ),
        )

        evaluator = ResearchWorkspaceConsumerProjectionReadinessEvaluator()
        report = evaluator.evaluate(plan)

        assert report.readiness == DEGRADED_READY
        assert report.executable is True
        assert report.issues[0].code == "degraded_dependency"
        assert report.reason == OPTIONAL_CONSTRAINTS_PRESENT

    def test_stale_usable_source_produces_degraded_ready(self):
        plan = _make_plan(
            required_sources=(
                ResearchWorkspaceConsumerProjectionExecutionPlanSource(
                    name="arxiv",
                    expired=False,
                    stale_usable=True,
                ),
            ),
        )

        evaluator = ResearchWorkspaceConsumerProjectionReadinessEvaluator()
        report = evaluator.evaluate(plan)

        assert report.readiness == DEGRADED_READY
        assert report.executable is True
        assert report.issues[0].code == "stale_usable_source"
        assert report.reason == OPTIONAL_CONSTRAINTS_PRESENT


class TestMissingDependency:
    """An unsatisfied required dependency blocks execution."""

    def test_missing_dependency_produces_blocked(self):
        plan = _make_plan(
            required_dependencies=(
                ResearchWorkspaceConsumerProjectionExecutionPlanDependency(
                    name="cache",
                    satisfied=False,
                ),
            ),
        )

        evaluator = ResearchWorkspaceConsumerProjectionReadinessEvaluator()
        report = evaluator.evaluate(plan)

        assert report.readiness == BLOCKED
        assert report.executable is False
        assert report.issues[0].code == "missing_dependency"
        assert report.reason == REQUIRED_DEPENDENCY_MISSING


class TestExpiredRequiredSource:
    """An expired required source blocks execution."""

    def test_expired_source_produces_blocked(self):
        plan = _make_plan(
            required_sources=(
                ResearchWorkspaceConsumerProjectionExecutionPlanSource(
                    name="arxiv",
                    expired=True,
                ),
            ),
        )

        evaluator = ResearchWorkspaceConsumerProjectionReadinessEvaluator()
        report = evaluator.evaluate(plan)

        assert report.readiness == BLOCKED
        assert report.executable is False
        assert report.issues[0].code == "expired_source"
        assert report.reason == REQUIRED_SOURCE_UNAVAILABLE

    def test_budget_exhausted_produces_blocked(self):
        plan = _make_plan(budget_available=False)

        evaluator = ResearchWorkspaceConsumerProjectionReadinessEvaluator()
        report = evaluator.evaluate(plan)

        assert report.readiness == BLOCKED
        assert report.executable is False
        assert report.issues[0].code == "budget_exhausted"
        assert report.reason == BUDGET_EXHAUSTED_REASON

    def test_disabled_projection_produces_blocked(self):
        plan = _make_plan(enabled=False)

        evaluator = ResearchWorkspaceConsumerProjectionReadinessEvaluator()
        report = evaluator.evaluate(plan)

        assert report.readiness == BLOCKED
        assert report.executable is False
        assert report.issues[0].code == "projection_disabled"
        assert report.reason == EXECUTION_DISABLED

    def test_impossible_mandatory_stage_produces_blocked(self):
        plan = _make_plan(
            stages=(
                ResearchWorkspaceConsumerProjectionExecutionPlanStage(
                    name="fetch",
                    requirement=MANDATORY,
                    will_execute=False,
                ),
            ),
        )

        evaluator = ResearchWorkspaceConsumerProjectionReadinessEvaluator()
        report = evaluator.evaluate(plan)

        assert report.readiness == BLOCKED
        assert report.executable is False
        assert report.issues[0].code == "mandatory_stage_impossible"
        assert report.reason == REQUIRED_DEPENDENCY_MISSING


class TestMultipleIssues:
    """Every distinct detected problem becomes its own issue."""

    def test_multiple_issues_are_all_collected(self):
        plan = _make_plan(
            required_dependencies=(
                ResearchWorkspaceConsumerProjectionExecutionPlanDependency(
                    name="cache",
                    satisfied=False,
                ),
            ),
            required_sources=(
                ResearchWorkspaceConsumerProjectionExecutionPlanSource(
                    name="arxiv",
                    expired=True,
                ),
            ),
            budget_available=False,
        )

        evaluator = ResearchWorkspaceConsumerProjectionReadinessEvaluator()
        report = evaluator.evaluate(plan)

        codes = [issue.code for issue in report.issues]

        assert codes == [
            "missing_dependency",
            "expired_source",
            "budget_exhausted",
        ]
        assert report.reason == REQUIRED_DEPENDENCY_MISSING


class TestReasonResolution:
    """The primary reason follows the documented blocking priority:

    EXECUTION_DISABLED > REQUIRED_DEPENDENCY_MISSING >
    REQUIRED_SOURCE_UNAVAILABLE > BUDGET_EXHAUSTED

    Issues stay a complete list of everything detected; reason is
    only the single highest-priority cause.
    """

    def _blocked_everything_plan(self):
        return _make_plan(
            enabled=False,
            required_dependencies=(
                ResearchWorkspaceConsumerProjectionExecutionPlanDependency(
                    name="cache",
                    satisfied=False,
                ),
            ),
            required_sources=(
                ResearchWorkspaceConsumerProjectionExecutionPlanSource(
                    name="arxiv",
                    expired=True,
                ),
            ),
            budget_available=False,
        )

    def test_disabled_projection_has_highest_priority(self):
        plan = self._blocked_everything_plan()

        evaluator = ResearchWorkspaceConsumerProjectionReadinessEvaluator()
        report = evaluator.evaluate(plan)

        assert report.reason == EXECUTION_DISABLED

    def test_missing_dependency_outranks_source_and_budget(self):
        plan = _make_plan(
            required_dependencies=(
                ResearchWorkspaceConsumerProjectionExecutionPlanDependency(
                    name="cache",
                    satisfied=False,
                ),
            ),
            required_sources=(
                ResearchWorkspaceConsumerProjectionExecutionPlanSource(
                    name="arxiv",
                    expired=True,
                ),
            ),
            budget_available=False,
        )

        evaluator = ResearchWorkspaceConsumerProjectionReadinessEvaluator()
        report = evaluator.evaluate(plan)

        assert report.reason == REQUIRED_DEPENDENCY_MISSING

    def test_missing_source_outranks_budget(self):
        plan = _make_plan(
            required_sources=(
                ResearchWorkspaceConsumerProjectionExecutionPlanSource(
                    name="arxiv",
                    expired=True,
                ),
            ),
            budget_available=False,
        )

        evaluator = ResearchWorkspaceConsumerProjectionReadinessEvaluator()
        report = evaluator.evaluate(plan)

        assert report.reason == REQUIRED_SOURCE_UNAVAILABLE

    def test_budget_exhausted_is_the_reason_when_nothing_else_blocks(self):
        plan = _make_plan(budget_available=False)

        evaluator = ResearchWorkspaceConsumerProjectionReadinessEvaluator()
        report = evaluator.evaluate(plan)

        assert report.reason == BUDGET_EXHAUSTED_REASON

    def test_issues_remain_the_complete_list_regardless_of_reason(self):
        plan = self._blocked_everything_plan()

        evaluator = ResearchWorkspaceConsumerProjectionReadinessEvaluator()
        report = evaluator.evaluate(plan)

        codes = [issue.code for issue in report.issues]

        assert codes == [
            "projection_disabled",
            "missing_dependency",
            "expired_source",
            "budget_exhausted",
        ]
        assert report.reason == EXECUTION_DISABLED

    def test_only_one_primary_reason_is_returned(self):
        plan = self._blocked_everything_plan()

        evaluator = ResearchWorkspaceConsumerProjectionReadinessEvaluator()
        report = evaluator.evaluate(plan)

        assert isinstance(
            report.reason,
            ResearchWorkspaceConsumerProjectionReadinessReason,
        )

    def test_reason_resolution_is_stable_across_repeated_evaluations(self):
        plan = self._blocked_everything_plan()

        evaluator = ResearchWorkspaceConsumerProjectionReadinessEvaluator()

        first = evaluator.evaluate(plan)
        second = evaluator.evaluate(plan)

        assert first.reason == second.reason == EXECUTION_DISABLED


class TestDuplicateIssues:
    """Identical issues are only emitted once."""

    def test_duplicate_missing_dependency_issue_not_repeated(self):
        plan = _make_plan(
            required_dependencies=(
                ResearchWorkspaceConsumerProjectionExecutionPlanDependency(
                    name="cache",
                    satisfied=False,
                ),
                ResearchWorkspaceConsumerProjectionExecutionPlanDependency(
                    name="cache",
                    satisfied=False,
                ),
            ),
        )

        evaluator = ResearchWorkspaceConsumerProjectionReadinessEvaluator()
        report = evaluator.evaluate(plan)

        assert len(report.issues) == 1
        assert report.issues[0].code == "missing_dependency"

    def test_distinct_dependency_names_produce_distinct_issues(self):
        plan = _make_plan(
            required_dependencies=(
                ResearchWorkspaceConsumerProjectionExecutionPlanDependency(
                    name="cache",
                    satisfied=False,
                ),
                ResearchWorkspaceConsumerProjectionExecutionPlanDependency(
                    name="index",
                    satisfied=False,
                ),
            ),
        )

        evaluator = ResearchWorkspaceConsumerProjectionReadinessEvaluator()
        report = evaluator.evaluate(plan)

        assert len(report.issues) == 2


class TestStableIssueOrdering:
    """Issues are ordered by evaluation stage, deterministically."""

    def test_issue_order_follows_enabled_dependency_source_budget_stage(
        self,
    ):
        plan = _make_plan(
            enabled=False,
            required_dependencies=(
                ResearchWorkspaceConsumerProjectionExecutionPlanDependency(
                    name="cache",
                    satisfied=False,
                ),
            ),
            required_sources=(
                ResearchWorkspaceConsumerProjectionExecutionPlanSource(
                    name="arxiv",
                    expired=True,
                ),
            ),
            budget_available=False,
            stages=(
                ResearchWorkspaceConsumerProjectionExecutionPlanStage(
                    name="fetch",
                    requirement=MANDATORY,
                    will_execute=False,
                ),
            ),
        )

        evaluator = ResearchWorkspaceConsumerProjectionReadinessEvaluator()
        report = evaluator.evaluate(plan)

        codes = [issue.code for issue in report.issues]

        assert codes == [
            "projection_disabled",
            "missing_dependency",
            "expired_source",
            "budget_exhausted",
            "mandatory_stage_impossible",
        ]

    def test_issue_order_is_stable_across_repeated_evaluations(self):
        plan = _make_plan(
            required_dependencies=(
                ResearchWorkspaceConsumerProjectionExecutionPlanDependency(
                    name="cache",
                    satisfied=False,
                ),
            ),
            required_sources=(
                ResearchWorkspaceConsumerProjectionExecutionPlanSource(
                    name="arxiv",
                    expired=True,
                ),
            ),
        )

        evaluator = ResearchWorkspaceConsumerProjectionReadinessEvaluator()

        first = evaluator.evaluate(plan)
        second = evaluator.evaluate(plan)

        assert first.issues == second.issues


class TestBlockedProperty:
    """The derived `blocked` property mirrors the readiness classification."""

    def test_blocked_true_when_readiness_is_blocked(self):
        plan = _make_plan(enabled=False)

        evaluator = ResearchWorkspaceConsumerProjectionReadinessEvaluator()
        report = evaluator.evaluate(plan)

        assert report.blocked is True

    def test_blocked_false_when_readiness_is_ready(self):
        plan = _make_plan()

        evaluator = ResearchWorkspaceConsumerProjectionReadinessEvaluator()
        report = evaluator.evaluate(plan)

        assert report.blocked is False

    def test_blocked_false_when_readiness_is_degraded_ready(self):
        plan = _make_plan(
            stages=(
                ResearchWorkspaceConsumerProjectionExecutionPlanStage(
                    name="enrich",
                    requirement=OPTIONAL,
                    will_execute=False,
                ),
            ),
        )

        evaluator = ResearchWorkspaceConsumerProjectionReadinessEvaluator()
        report = evaluator.evaluate(plan)

        assert report.blocked is False


class TestDeterminism:
    """Evaluating the same plan twice yields equal reports."""

    def test_equivalent_plans_produce_equivalent_reports(self):
        plan = _make_plan(
            required_dependencies=(
                ResearchWorkspaceConsumerProjectionExecutionPlanDependency(
                    name="cache",
                    satisfied=True,
                    degraded=True,
                ),
            ),
        )

        evaluator = ResearchWorkspaceConsumerProjectionReadinessEvaluator()

        first = evaluator.evaluate(plan)
        second = evaluator.evaluate(plan)

        assert first == second


class TestArchitecturalBoundaries:
    """Structural guarantees: no state, no mutation, no side effects."""

    def test_evaluator_has_no_external_dependencies(self):
        evaluator = ResearchWorkspaceConsumerProjectionReadinessEvaluator()

        assert evaluator.__dict__ == {}

    def test_evaluator_does_not_mutate_plan(self):
        plan = _make_plan(
            required_dependencies=(
                ResearchWorkspaceConsumerProjectionExecutionPlanDependency(
                    name="cache",
                    satisfied=False,
                ),
            ),
        )

        plan_dict_before = plan.to_dict()

        evaluator = ResearchWorkspaceConsumerProjectionReadinessEvaluator()
        evaluator.evaluate(plan)

        assert plan.to_dict() == plan_dict_before

    def test_report_carries_no_execution_outcome(self):
        # The report is a pure readiness classification: it exposes
        # no execution result, output, or receipt of any kind.
        plan = _make_plan()

        evaluator = ResearchWorkspaceConsumerProjectionReadinessEvaluator()
        report = evaluator.evaluate(plan)

        assert set(report.to_dict().keys()) == {
            "projection_name",
            "readiness",
            "executable",
            "reason",
            "issues",
            "blocked",
        }
