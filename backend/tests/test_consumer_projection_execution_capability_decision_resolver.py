from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapability,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityClassification,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionReason,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionResolver,
    ResearchWorkspaceConsumerProjectionExecutionCapabilitySnapshotPackage,
)


CAPABLE = ResearchWorkspaceConsumerProjectionExecutionCapability.CAPABLE
LIMITED = ResearchWorkspaceConsumerProjectionExecutionCapability.LIMITED
INCAPABLE = ResearchWorkspaceConsumerProjectionExecutionCapability.INCAPABLE

STANDARD = (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityClassification.STANDARD
)
RESTRICTED = (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityClassification.RESTRICTED
)
UNSUPPORTED = (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityClassification.UNSUPPORTED
)

ACCEPT = ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision.ACCEPT
REVIEW = ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision.REVIEW
REJECT = ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision.REJECT

STANDARD_CAPABILITY = (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionReason.STANDARD_CAPABILITY
)
RESTRICTED_CAPABILITY = (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionReason.RESTRICTED_CAPABILITY
)
UNSUPPORTED_CAPABILITY = (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionReason.UNSUPPORTED_CAPABILITY
)


def _make_package(
    *,
    projection_name="workspace.bootstrap",
    capability=CAPABLE,
    classification=STANDARD,
    executable=True,
    title="Standard Capability",
    description="Projection supports normal execution.",
):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilitySnapshotPackage(
        projection_name=projection_name,
        capability=capability,
        classification=classification,
        executable=executable,
        title=title,
        description=description,
    )


class TestStandardClassification:
    """STANDARD resolves to ACCEPT."""

    def test_standard_produces_accept(self):
        package = _make_package(
            capability=CAPABLE, classification=STANDARD, executable=True
        )

        resolver = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionResolver()
        )
        report = resolver.resolve(package)

        assert report.decision == ACCEPT
        assert report.reason == STANDARD_CAPABILITY


class TestRestrictedClassification:
    """RESTRICTED resolves to REVIEW."""

    def test_restricted_produces_review(self):
        package = _make_package(
            capability=LIMITED,
            classification=RESTRICTED,
            executable=False,
            title="Restricted Capability",
            description="Projection requires additional approval before execution.",
        )

        resolver = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionResolver()
        )
        report = resolver.resolve(package)

        assert report.decision == REVIEW
        assert report.reason == RESTRICTED_CAPABILITY


class TestUnsupportedClassification:
    """UNSUPPORTED resolves to REJECT."""

    def test_unsupported_produces_reject(self):
        package = _make_package(
            capability=INCAPABLE,
            classification=UNSUPPORTED,
            executable=False,
            title="Unsupported Capability",
            description="Projection is not capable of execution.",
        )

        resolver = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionResolver()
        )
        report = resolver.resolve(package)

        assert report.decision == REJECT
        assert report.reason == UNSUPPORTED_CAPABILITY


class TestProjectionPreserved:
    """projection_name is copied from the capability snapshot package."""

    def test_projection_name_is_preserved(self):
        package = _make_package(projection_name="workspace.attention")

        resolver = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionResolver()
        )
        report = resolver.resolve(package)

        assert report.projection_name == "workspace.attention"


class TestExecutablePreserved:
    """executable is copied from the package, not recomputed."""

    def test_executable_flag_true_is_preserved(self):
        package = _make_package(
            capability=CAPABLE, classification=STANDARD, executable=True
        )

        resolver = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionResolver()
        )
        report = resolver.resolve(package)

        assert report.executable is True

    def test_executable_flag_false_is_preserved(self):
        package = _make_package(
            capability=INCAPABLE,
            classification=UNSUPPORTED,
            executable=False,
        )

        resolver = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionResolver()
        )
        report = resolver.resolve(package)

        assert report.executable is False


class TestDeterminism:
    """Resolving the same package twice yields equal reports."""

    def test_equivalent_package_produces_equivalent_reports(self):
        package = _make_package(
            capability=LIMITED, classification=RESTRICTED, executable=False
        )

        resolver = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionResolver()
        )

        first = resolver.resolve(package)
        second = resolver.resolve(package)

        assert first == second


class TestArchitecturalBoundaries:
    """Structural guarantees: no state, no mutation, no side effects."""

    def test_resolver_has_no_external_dependencies(self):
        resolver = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionResolver()
        )

        assert resolver.__dict__ == {}

    def test_resolver_does_not_mutate_package(self):
        package = _make_package(
            capability=LIMITED, classification=RESTRICTED, executable=False
        )
        package_dict_before = package.to_dict()

        resolver = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionResolver()
        )
        resolver.resolve(package)

        assert package.to_dict() == package_dict_before

    def test_report_carries_no_scheduler_or_approval_state(self):
        package = _make_package(
            capability=CAPABLE, classification=STANDARD, executable=True
        )

        resolver = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionResolver()
        )
        report = resolver.resolve(package)

        assert set(report.to_dict().keys()) == {
            "projection_name",
            "decision",
            "reason",
            "executable",
        }
