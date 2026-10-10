from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapability,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityClassification,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityClassificationResolver,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityProfile,
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


def _make_profile(
    *,
    projection_name="workspace.bootstrap",
    capability=CAPABLE,
    executable=True,
    profile="EXECUTION_READY",
):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityProfile(
        projection_name=projection_name,
        capability=capability,
        executable=executable,
        profile=profile,
    )


class TestExecutionReadyProfile:
    """EXECUTION_READY resolves to STANDARD."""

    def test_execution_ready_produces_standard(self):
        profile = _make_profile(
            capability=CAPABLE, executable=True, profile="EXECUTION_READY"
        )

        resolver = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityClassificationResolver()
        )
        report = resolver.resolve(profile)

        assert report.classification == STANDARD


class TestApprovalRequiredProfile:
    """APPROVAL_REQUIRED resolves to RESTRICTED."""

    def test_approval_required_produces_restricted(self):
        profile = _make_profile(
            capability=LIMITED,
            executable=False,
            profile="APPROVAL_REQUIRED",
        )

        resolver = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityClassificationResolver()
        )
        report = resolver.resolve(profile)

        assert report.classification == RESTRICTED


class TestExecutionBlockedProfile:
    """EXECUTION_BLOCKED resolves to UNSUPPORTED."""

    def test_execution_blocked_produces_unsupported(self):
        profile = _make_profile(
            capability=INCAPABLE,
            executable=False,
            profile="EXECUTION_BLOCKED",
        )

        resolver = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityClassificationResolver()
        )
        report = resolver.resolve(profile)

        assert report.classification == UNSUPPORTED


class TestProjectionPreserved:
    """projection_name is copied from the capability profile."""

    def test_projection_name_is_preserved(self):
        profile = _make_profile(projection_name="workspace.attention")

        resolver = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityClassificationResolver()
        )
        report = resolver.resolve(profile)

        assert report.projection_name == "workspace.attention"


class TestProfilePreserved:
    """profile is copied from the capability profile, not recomputed."""

    def test_profile_is_preserved(self):
        profile = _make_profile(profile="APPROVAL_REQUIRED")

        resolver = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityClassificationResolver()
        )
        report = resolver.resolve(profile)

        assert report.profile == "APPROVAL_REQUIRED"


class TestExecutablePreserved:
    """executable is copied from the capability profile, not recomputed."""

    def test_executable_flag_true_is_preserved(self):
        profile = _make_profile(
            capability=CAPABLE, executable=True, profile="EXECUTION_READY"
        )

        resolver = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityClassificationResolver()
        )
        report = resolver.resolve(profile)

        assert report.executable is True

    def test_executable_flag_false_is_preserved(self):
        profile = _make_profile(
            capability=INCAPABLE,
            executable=False,
            profile="EXECUTION_BLOCKED",
        )

        resolver = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityClassificationResolver()
        )
        report = resolver.resolve(profile)

        assert report.executable is False


class TestDeterminism:
    """Resolving the same profile twice yields equal reports."""

    def test_equivalent_profile_produces_equivalent_reports(self):
        profile = _make_profile(
            capability=LIMITED,
            executable=False,
            profile="APPROVAL_REQUIRED",
        )

        resolver = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityClassificationResolver()
        )

        first = resolver.resolve(profile)
        second = resolver.resolve(profile)

        assert first == second


class TestArchitecturalBoundaries:
    """Structural guarantees: no state, no mutation, no side effects."""

    def test_resolver_has_no_external_dependencies(self):
        resolver = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityClassificationResolver()
        )

        assert resolver.__dict__ == {}

    def test_resolver_does_not_mutate_profile(self):
        profile = _make_profile(
            capability=LIMITED,
            executable=False,
            profile="APPROVAL_REQUIRED",
        )
        profile_dict_before = profile.to_dict()

        resolver = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityClassificationResolver()
        )
        resolver.resolve(profile)

        assert profile.to_dict() == profile_dict_before

    def test_report_carries_no_scheduler_or_approval_state(self):
        profile = _make_profile(
            capability=CAPABLE, executable=True, profile="EXECUTION_READY"
        )

        resolver = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityClassificationResolver()
        )
        report = resolver.resolve(profile)

        assert set(report.to_dict().keys()) == {
            "projection_name",
            "classification",
            "profile",
            "executable",
        }
