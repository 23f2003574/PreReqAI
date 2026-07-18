from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapability,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityPackage,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityProfileBuilder,
)


CAPABLE = ResearchWorkspaceConsumerProjectionExecutionCapability.CAPABLE
LIMITED = ResearchWorkspaceConsumerProjectionExecutionCapability.LIMITED
INCAPABLE = ResearchWorkspaceConsumerProjectionExecutionCapability.INCAPABLE


def _make_package(
    *,
    projection_name="workspace.bootstrap",
    capability=CAPABLE,
    executable=True,
    title="Execution Capable",
    description="Projection is capable of execution.",
):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityPackage(
        projection_name=projection_name,
        capability=capability,
        executable=executable,
        title=title,
        description=description,
    )


class TestCapablePackage:
    """CAPABLE resolves to the EXECUTION_READY profile."""

    def test_capable_produces_execution_ready(self):
        package = _make_package(capability=CAPABLE, executable=True)

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityProfileBuilder()
        )
        profile = builder.build(package)

        assert profile.profile == "EXECUTION_READY"


class TestLimitedPackage:
    """LIMITED resolves to the APPROVAL_REQUIRED profile."""

    def test_limited_produces_approval_required(self):
        package = _make_package(
            capability=LIMITED,
            executable=False,
            title="Limited Execution",
            description="Projection requires additional approval before execution.",
        )

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityProfileBuilder()
        )
        profile = builder.build(package)

        assert profile.profile == "APPROVAL_REQUIRED"


class TestIncapablePackage:
    """INCAPABLE resolves to the EXECUTION_BLOCKED profile."""

    def test_incapable_produces_execution_blocked(self):
        package = _make_package(
            capability=INCAPABLE,
            executable=False,
            title="Execution Incapable",
            description="Projection cannot be executed.",
        )

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityProfileBuilder()
        )
        profile = builder.build(package)

        assert profile.profile == "EXECUTION_BLOCKED"


class TestProjectionPreserved:
    """projection_name is copied from the capability package."""

    def test_projection_name_is_preserved(self):
        package = _make_package(projection_name="workspace.attention")

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityProfileBuilder()
        )
        profile = builder.build(package)

        assert profile.projection_name == "workspace.attention"


class TestExecutablePreserved:
    """executable is copied from the capability package, not recomputed."""

    def test_executable_flag_true_is_preserved(self):
        package = _make_package(capability=CAPABLE, executable=True)

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityProfileBuilder()
        )
        profile = builder.build(package)

        assert profile.executable is True

    def test_executable_flag_false_is_preserved(self):
        package = _make_package(capability=INCAPABLE, executable=False)

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityProfileBuilder()
        )
        profile = builder.build(package)

        assert profile.executable is False


class TestCapabilityPreserved:
    """capability is copied from the capability package, not recomputed."""

    def test_capability_is_preserved(self):
        package = _make_package(capability=LIMITED, executable=False)

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityProfileBuilder()
        )
        profile = builder.build(package)

        assert profile.capability == LIMITED


class TestDeterminism:
    """Building the same package twice yields equal profiles."""

    def test_equivalent_package_produces_equivalent_profiles(self):
        package = _make_package(capability=LIMITED, executable=False)

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityProfileBuilder()
        )

        first = builder.build(package)
        second = builder.build(package)

        assert first == second


class TestArchitecturalBoundaries:
    """Structural guarantees: no state, no mutation, no side effects."""

    def test_builder_has_no_external_dependencies(self):
        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityProfileBuilder()
        )

        assert builder.__dict__ == {}

    def test_builder_does_not_mutate_package(self):
        package = _make_package()
        package_dict_before = package.to_dict()

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityProfileBuilder()
        )
        builder.build(package)

        assert package.to_dict() == package_dict_before

    def test_profile_carries_no_scheduler_or_approval_state(self):
        package = _make_package()

        builder = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityProfileBuilder()
        )
        profile = builder.build(package)

        assert set(profile.to_dict().keys()) == {
            "projection_name",
            "capability",
            "executable",
            "profile",
        }
