import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityDecisionPackage,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryValidationError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryValidator,
)


ACCEPT = ResearchWorkspaceConsumerProjectionExecutionCapabilityDecision.ACCEPT


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


def _inject(registry, key, package):
    """Place a package directly into registry storage, bypassing
    register()'s own validation, to simulate a corrupted entry."""
    registry._packages[key] = package


class TestEmptyRegistry:
    """An empty registry validates as trivially valid."""

    def test_empty_registry(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry()
        validator = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryValidator()

        report = validator.validate(registry)

        assert report.total_packages == 0
        assert report.valid_packages == 0
        assert report.invalid_packages == 0
        assert report.is_valid is True


class TestFullyValidRegistry:
    """A registry of well-formed packages validates cleanly."""

    def test_fully_valid_registry(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry()
        registry.register(_make_package(projection_name="workspace.bootstrap"))
        registry.register(_make_package(projection_name="workspace.attention"))

        validator = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryValidator()
        report = validator.validate(registry)

        assert report.total_packages == 2
        assert report.valid_packages == 2
        assert report.invalid_packages == 0
        assert report.is_valid is True


class TestInvalidProjectionName:
    """A package with an empty projection name is invalid."""

    def test_invalid_projection_name(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry()
        _inject(
            registry,
            "workspace.bootstrap",
            _make_package(projection_name=""),
        )

        validator = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryValidator()
        report = validator.validate(registry)

        assert report.total_packages == 1
        assert report.valid_packages == 0
        assert report.invalid_packages == 1
        assert report.is_valid is False


class TestInvalidTitle:
    """A package with an empty title is invalid."""

    def test_invalid_title(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry()
        registry.register(_make_package(title=""))

        validator = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryValidator()
        report = validator.validate(registry)

        assert report.invalid_packages == 1
        assert report.is_valid is False


class TestInvalidMessage:
    """A package with an empty message is invalid."""

    def test_invalid_message(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry()
        registry.register(_make_package(message=""))

        validator = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryValidator()
        report = validator.validate(registry)

        assert report.invalid_packages == 1
        assert report.is_valid is False


class TestInvalidDecision:
    """A package whose decision is not a valid enum member is invalid."""

    def test_invalid_decision(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry()
        registry.register(_make_package(decision="accept"))

        validator = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryValidator()
        report = validator.validate(registry)

        assert report.invalid_packages == 1
        assert report.is_valid is False


class TestInvalidExecutable:
    """A package whose executable flag is not a boolean is invalid."""

    def test_invalid_executable(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry()
        registry.register(_make_package(executable="true"))

        validator = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryValidator()
        report = validator.validate(registry)

        assert report.invalid_packages == 1
        assert report.is_valid is False


class TestPackageCounts:
    """Mixed valid and invalid packages produce accurate counts."""

    def test_mixed_registry_counts(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry()
        registry.register(_make_package(projection_name="workspace.bootstrap"))
        registry.register(_make_package(projection_name="workspace.attention", title=""))
        _inject(
            registry,
            "session.actions",
            _make_package(projection_name="", message=""),
        )

        validator = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryValidator()
        report = validator.validate(registry)

        assert report.total_packages == 3
        assert report.valid_packages == 1
        assert report.invalid_packages == 2
        assert report.is_valid is False


class TestMalformedEntry:
    """An entry that cannot be inspected raises rather than being counted."""

    def test_malformed_entry_raises_error(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry()
        _inject(registry, "workspace.bootstrap", "not-a-package")

        validator = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryValidator()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryValidationError
        ):
            validator.validate(registry)


class TestInvalidRegistry:
    """A None or non-registry value is rejected."""

    def test_reject_none_registry(self):
        validator = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryValidator()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryValidationError
        ):
            validator.validate(None)


class TestRegistryUnchanged:
    """Validation never mutates the registry or its packages."""

    def test_registry_remains_unchanged(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry()
        package = _make_package()
        registry.register(package)
        package_dict = package.to_dict()

        validator = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryValidator()
        validator.validate(registry)

        assert registry.list_projection_names() == ("workspace.bootstrap",)
        assert package.to_dict() == package_dict


class TestDeterminism:
    """Validating the same registry state twice agrees."""

    def test_repeated_validation_is_deterministic(self):
        registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistry()
        registry.register(_make_package())

        validator = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryValidator()

        first = validator.validate(registry)
        second = validator.validate(registry)

        assert first == second
