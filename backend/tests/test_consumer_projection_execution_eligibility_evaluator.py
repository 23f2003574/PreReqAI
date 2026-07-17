from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionEligibility,
    ResearchWorkspaceConsumerProjectionExecutionEligibilityEvaluator,
    ResearchWorkspaceConsumerProjectionExecutionEligibilityReason,
    ResearchWorkspaceConsumerProjectionReadiness,
    ResearchWorkspaceConsumerProjectionReadinessReason,
    ResearchWorkspaceConsumerProjectionReadinessReport,
)


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

ELIGIBLE = ResearchWorkspaceConsumerProjectionExecutionEligibility.ELIGIBLE
CONDITIONALLY_ELIGIBLE = (
    ResearchWorkspaceConsumerProjectionExecutionEligibility.CONDITIONALLY_ELIGIBLE
)
INELIGIBLE = (
    ResearchWorkspaceConsumerProjectionExecutionEligibility.INELIGIBLE
)

READY_REASON = (
    ResearchWorkspaceConsumerProjectionExecutionEligibilityReason.READY
)
DEGRADED_READY_REASON = (
    ResearchWorkspaceConsumerProjectionExecutionEligibilityReason.DEGRADED_READY
)
BLOCKED_REASON = (
    ResearchWorkspaceConsumerProjectionExecutionEligibilityReason.BLOCKED
)


def _make_readiness(
    *,
    projection_name="workspace.bootstrap",
    readiness=READY,
    executable=True,
    reason=ALL_REQUIREMENTS_MET,
):
    return ResearchWorkspaceConsumerProjectionReadinessReport(
        projection_name=projection_name,
        readiness=readiness,
        executable=executable,
        reason=reason,
    )


class TestReadyReadiness:
    """READY readiness resolves to ELIGIBLE."""

    def test_ready_produces_eligible(self):
        readiness = _make_readiness(
            readiness=READY,
            executable=True,
            reason=ALL_REQUIREMENTS_MET,
        )

        evaluator = (
            ResearchWorkspaceConsumerProjectionExecutionEligibilityEvaluator()
        )
        report = evaluator.evaluate(readiness)

        assert report.eligibility == ELIGIBLE
        assert report.reason == READY_REASON


class TestDegradedReadyReadiness:
    """DEGRADED_READY readiness resolves to CONDITIONALLY_ELIGIBLE."""

    def test_degraded_ready_produces_conditionally_eligible(self):
        readiness = _make_readiness(
            readiness=DEGRADED_READY,
            executable=True,
            reason=OPTIONAL_CONSTRAINTS_PRESENT,
        )

        evaluator = (
            ResearchWorkspaceConsumerProjectionExecutionEligibilityEvaluator()
        )
        report = evaluator.evaluate(readiness)

        assert report.eligibility == CONDITIONALLY_ELIGIBLE
        assert report.reason == DEGRADED_READY_REASON


class TestBlockedReadiness:
    """BLOCKED readiness resolves to INELIGIBLE."""

    def test_blocked_produces_ineligible(self):
        readiness = _make_readiness(
            readiness=BLOCKED,
            executable=False,
            reason=REQUIRED_DEPENDENCY_MISSING,
        )

        evaluator = (
            ResearchWorkspaceConsumerProjectionExecutionEligibilityEvaluator()
        )
        report = evaluator.evaluate(readiness)

        assert report.eligibility == INELIGIBLE
        assert report.reason == BLOCKED_REASON


class TestProjectionPreserved:
    """projection_name is copied from the readiness report."""

    def test_projection_name_is_preserved(self):
        readiness = _make_readiness(projection_name="workspace.attention")

        evaluator = (
            ResearchWorkspaceConsumerProjectionExecutionEligibilityEvaluator()
        )
        report = evaluator.evaluate(readiness)

        assert report.projection_name == "workspace.attention"


class TestExecutablePreserved:
    """executable is copied from the readiness report, not recomputed."""

    def test_executable_true_is_preserved(self):
        readiness = _make_readiness(readiness=READY, executable=True)

        evaluator = (
            ResearchWorkspaceConsumerProjectionExecutionEligibilityEvaluator()
        )
        report = evaluator.evaluate(readiness)

        assert report.executable is True

    def test_executable_false_is_preserved(self):
        readiness = _make_readiness(readiness=BLOCKED, executable=False)

        evaluator = (
            ResearchWorkspaceConsumerProjectionExecutionEligibilityEvaluator()
        )
        report = evaluator.evaluate(readiness)

        assert report.executable is False


class TestEligibleProperty:
    """The derived `eligible` property is false only when INELIGIBLE."""

    def test_eligible_true_when_eligible(self):
        readiness = _make_readiness(readiness=READY)

        evaluator = (
            ResearchWorkspaceConsumerProjectionExecutionEligibilityEvaluator()
        )
        report = evaluator.evaluate(readiness)

        assert report.eligible is True

    def test_eligible_true_when_conditionally_eligible(self):
        readiness = _make_readiness(readiness=DEGRADED_READY)

        evaluator = (
            ResearchWorkspaceConsumerProjectionExecutionEligibilityEvaluator()
        )
        report = evaluator.evaluate(readiness)

        assert report.eligible is True

    def test_eligible_false_when_ineligible(self):
        readiness = _make_readiness(readiness=BLOCKED, executable=False)

        evaluator = (
            ResearchWorkspaceConsumerProjectionExecutionEligibilityEvaluator()
        )
        report = evaluator.evaluate(readiness)

        assert report.eligible is False


class TestDeterminism:
    """Evaluating the same readiness report twice yields equal reports."""

    def test_equivalent_readiness_produces_equivalent_reports(self):
        readiness = _make_readiness(readiness=DEGRADED_READY)

        evaluator = (
            ResearchWorkspaceConsumerProjectionExecutionEligibilityEvaluator()
        )

        first = evaluator.evaluate(readiness)
        second = evaluator.evaluate(readiness)

        assert first == second


class TestArchitecturalBoundaries:
    """Structural guarantees: no state, no mutation, no side effects."""

    def test_evaluator_has_no_external_dependencies(self):
        evaluator = (
            ResearchWorkspaceConsumerProjectionExecutionEligibilityEvaluator()
        )

        assert evaluator.__dict__ == {}

    def test_evaluator_does_not_mutate_readiness(self):
        readiness = _make_readiness(readiness=DEGRADED_READY)
        readiness_dict_before = readiness.to_dict()

        evaluator = (
            ResearchWorkspaceConsumerProjectionExecutionEligibilityEvaluator()
        )
        evaluator.evaluate(readiness)

        assert readiness.to_dict() == readiness_dict_before

    def test_report_carries_no_execution_or_scheduling_state(self):
        readiness = _make_readiness(readiness=READY)

        evaluator = (
            ResearchWorkspaceConsumerProjectionExecutionEligibilityEvaluator()
        )
        report = evaluator.evaluate(readiness)

        assert set(report.to_dict().keys()) == {
            "projection_name",
            "eligibility",
            "reason",
            "executable",
            "eligible",
        }
