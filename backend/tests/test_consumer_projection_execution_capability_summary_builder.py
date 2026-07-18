from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapability,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityReason,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityReport,
    ResearchWorkspaceConsumerProjectionExecutionCapabilitySummaryBuilder,
)


CAPABLE = ResearchWorkspaceConsumerProjectionExecutionCapability.CAPABLE
LIMITED = ResearchWorkspaceConsumerProjectionExecutionCapability.LIMITED
INCAPABLE = ResearchWorkspaceConsumerProjectionExecutionCapability.INCAPABLE

READY_REASON = (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityReason.READY
)
APPROVAL_REQUIRED = (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityReason.APPROVAL_REQUIRED
)
EXECUTION_BLOCKED = (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityReason.EXECUTION_BLOCKED
)


def _make_capability(
    *,
    projection_name="workspace.bootstrap",
    capability=CAPABLE,
    reason=READY_REASON,
    executable=True,
):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityReport(
        projection_name=projection_name,
        capability=capability,
        reason=reason,
        executable=executable,
    )


class TestCapableCapability:
    """CAPABLE produces the execution-capable presentation."""

    def test_capable_summary(self):
        capability = _make_capability(
            capability=CAPABLE,
            reason=READY_REASON,
            executable=True,
        )

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilitySummaryBuilder()
        )
        summary = builder.build(capability)

        assert summary.title == "Execution Capable"
        assert (
            summary.description
            == "Projection is capable of execution."
        )


class TestLimitedCapability:
    """LIMITED produces the limited-execution presentation."""

    def test_limited_summary(self):
        capability = _make_capability(
            capability=LIMITED,
            reason=APPROVAL_REQUIRED,
            executable=False,
        )

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilitySummaryBuilder()
        )
        summary = builder.build(capability)

        assert summary.title == "Limited Execution"
        assert (
            summary.description
            == "Projection requires additional approval before execution."
        )


class TestIncapableCapability:
    """INCAPABLE produces the execution-incapable presentation."""

    def test_incapable_summary(self):
        capability = _make_capability(
            capability=INCAPABLE,
            reason=EXECUTION_BLOCKED,
            executable=False,
        )

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilitySummaryBuilder()
        )
        summary = builder.build(capability)

        assert summary.title == "Execution Incapable"
        assert summary.description == "Projection cannot be executed."


class TestCapabilityReasonPreserved:
    """capability and reason are copied from the report, not recomputed."""

    def test_capability_and_reason_are_preserved(self):
        capability = _make_capability(
            capability=LIMITED,
            reason=APPROVAL_REQUIRED,
            executable=False,
        )

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilitySummaryBuilder()
        )
        summary = builder.build(capability)

        assert summary.capability == LIMITED
        assert summary.reason == APPROVAL_REQUIRED


class TestProjectionPreserved:
    """projection_name is copied from the capability report."""

    def test_projection_name_is_preserved(self):
        capability = _make_capability(projection_name="workspace.attention")

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilitySummaryBuilder()
        )
        summary = builder.build(capability)

        assert summary.projection_name == "workspace.attention"


class TestExecutableFlagPreserved:
    """executable is copied from the capability report, not recomputed."""

    def test_executable_flag_true_is_preserved(self):
        capability = _make_capability(capability=CAPABLE, executable=True)

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilitySummaryBuilder()
        )
        summary = builder.build(capability)

        assert summary.executable is True

    def test_executable_flag_false_is_preserved(self):
        capability = _make_capability(capability=INCAPABLE, executable=False)

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilitySummaryBuilder()
        )
        summary = builder.build(capability)

        assert summary.executable is False


class TestDeterminism:
    """Building the same capability report twice yields equal summaries."""

    def test_equivalent_capability_produces_equivalent_summaries(self):
        capability = _make_capability(
            capability=LIMITED, reason=APPROVAL_REQUIRED
        )

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilitySummaryBuilder()
        )

        first = builder.build(capability)
        second = builder.build(capability)

        assert first == second


class TestArchitecturalBoundaries:
    """Structural guarantees: no state, no mutation, no side effects."""

    def test_builder_has_no_external_dependencies(self):
        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilitySummaryBuilder()
        )

        assert builder.__dict__ == {}

    def test_builder_does_not_mutate_capability(self):
        capability = _make_capability(
            capability=LIMITED, reason=APPROVAL_REQUIRED
        )
        capability_dict_before = capability.to_dict()

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilitySummaryBuilder()
        )
        builder.build(capability)

        assert capability.to_dict() == capability_dict_before

    def test_summary_carries_no_execution_state(self):
        capability = _make_capability(
            capability=CAPABLE, reason=READY_REASON
        )

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilitySummaryBuilder()
        )
        summary = builder.build(capability)

        assert set(summary.to_dict().keys()) == {
            "projection_name",
            "capability",
            "reason",
            "title",
            "description",
            "executable",
        }
