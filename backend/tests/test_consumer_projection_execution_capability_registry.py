import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionPackage,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryError,
)


ACCEPT = ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision.ACCEPT
REVIEW = ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision.REVIEW


def _make_package(
    *,
    projection_name="workspace.bootstrap",
    decision=ACCEPT,
    executable=True,
    title="Capability Accepted",
    message="Projection satisfies all execution capability requirements.",
):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionPackage(
        projection_name=projection_name,
        decision=decision,
        executable=executable,
        title=title,
        message=message,
    )


class TestRegistration:
    """A package can be registered and then retrieved."""

    def test_register_and_get(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry()
        package = _make_package()

        registry.register(package)

        assert registry.get("workspace.bootstrap") == package


class TestReplacement:
    """Registering an existing projection replaces the previous package."""

    def test_replace_existing_registration(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry()
        original = _make_package(decision=ACCEPT, title="Capability Accepted")
        replacement = _make_package(
            decision=REVIEW,
            executable=False,
            title="Capability Requires Review",
            message="Projection requires manual review before execution.",
        )

        registry.register(original)
        registry.register(replacement)

        assert registry.get("workspace.bootstrap") == replacement


class TestUnknownProjection:
    """Retrieving an unregistered projection raises a registry error."""

    def test_get_unknown_projection_raises_error(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryError
        ):
            registry.get("workspace.attention")


class TestContains:
    """contains() reports presence without mutating state."""

    def test_contains_known_and_unknown_projections(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry()
        registry.register(_make_package(projection_name="workspace.bootstrap"))

        assert registry.contains("workspace.bootstrap") is True
        assert registry.contains("workspace.attention") is False
        assert registry.list_projection_names() == ("workspace.bootstrap",)


class TestListProjectionNames:
    """Projection names are returned sorted and as an immutable tuple."""

    def test_list_projection_names_sorted_and_immutable(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry()
        registry.register(_make_package(projection_name="workspace.bootstrap"))
        registry.register(_make_package(projection_name="session.actions"))
        registry.register(_make_package(projection_name="workspace.attention"))

        names = registry.list_projection_names()

        assert names == (
            "session.actions",
            "workspace.attention",
            "workspace.bootstrap",
        )
        assert isinstance(names, tuple)


class TestEmptyProjectionName:
    """Registering an empty projection name is rejected."""

    def test_reject_empty_projection_name(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry()
        package = _make_package(projection_name="")

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryError
        ):
            registry.register(package)


class TestPackagePreservation:
    """The registry never modifies a stored package."""

    def test_registry_does_not_mutate_stored_package(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry()
        package = _make_package()
        package_dict = package.to_dict()

        registry.register(package)
        registry.get("workspace.bootstrap")
        registry.contains("workspace.bootstrap")
        registry.list_projection_names()

        assert package.to_dict() == package_dict


class TestDeterminism:
    """Repeated lookups against the same registry state agree."""

    def test_repeated_lookups_are_deterministic(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry()
        registry.register(_make_package())

        first = registry.get("workspace.bootstrap")
        second = registry.get("workspace.bootstrap")

        assert first == second
        assert registry.list_projection_names() == registry.list_projection_names()
