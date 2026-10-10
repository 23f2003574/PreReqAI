import dataclasses

from datetime import (
    datetime,
    timezone,
)

from types import SimpleNamespace

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspace,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSnapshot,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceValidationResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceValidator,
)


class _MemberRegistry:
    def __init__(self, *member_ids):
        self._member_ids = set(member_ids)

    def contains(self, member_id):
        return member_id in self._member_ids


def _build_workspace(
    workspace_id,
    name=None,
    description="A workspace.",
    binding_ids=(),
    template_ids=(),
    preset_ids=(),
    group_ids=(),
):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspace(
        workspace_id=workspace_id,
        name=name or workspace_id,
        description=description,
        binding_ids=binding_ids,
        template_ids=template_ids,
        preset_ids=preset_ids,
        group_ids=group_ids,
    )


def _build_validator(
    binding_ids=("binding-a",),
    template_ids=("template-a",),
    preset_ids=("preset-a",),
    group_ids=("group-a",),
):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceValidator(
        _MemberRegistry(*binding_ids),
        _MemberRegistry(*template_ids),
        _MemberRegistry(*preset_ids),
        _MemberRegistry(*group_ids),
    )


class TestValidWorkspace:
    def test_valid_workspace(self):
        validator = _build_validator()

        result = validator.validate(
            _build_workspace(
                "workspace-1",
                binding_ids=("binding-a",),
                template_ids=("template-a",),
                preset_ids=("preset-a",),
                group_ids=("group-a",),
            )
        )

        assert isinstance(result, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceValidationResult)
        assert result.valid is True
        assert result.violations == ()

    def test_none_workspace(self):
        validator = _build_validator()

        result = validator.validate(None)

        assert result.valid is False
        assert any(v.code == "MISSING_WORKSPACE" for v in result.violations)


class TestMissingWorkspaceIdentity:
    def test_missing_workspace_id(self):
        validator = _build_validator()

        malformed = SimpleNamespace(
            workspace_id="   ",
            name="Workspace",
            binding_ids=(),
            template_ids=(),
            preset_ids=(),
            group_ids=(),
        )

        result = validator.validate(malformed)

        assert result.valid is False
        assert any(v.code == "MISSING_WORKSPACE_ID" for v in result.violations)

    def test_missing_workspace_name(self):
        validator = _build_validator()

        malformed = SimpleNamespace(
            workspace_id="workspace-1",
            name=None,
            binding_ids=(),
            template_ids=(),
            preset_ids=(),
            group_ids=(),
        )

        result = validator.validate(malformed)

        assert result.valid is False
        assert any(v.code == "MISSING_WORKSPACE_NAME" for v in result.violations)


class TestUnknownResource:
    def test_unknown_binding(self):
        validator = _build_validator()

        result = validator.validate(_build_workspace("workspace-1", binding_ids=("binding-does-not-exist",)))

        assert result.valid is False
        assert any(v.code == "UNKNOWN_BINDING" for v in result.violations)

    def test_unknown_template(self):
        validator = _build_validator()

        result = validator.validate(_build_workspace("workspace-1", template_ids=("template-does-not-exist",)))

        assert result.valid is False
        assert any(v.code == "UNKNOWN_TEMPLATE" for v in result.violations)

    def test_unknown_preset(self):
        validator = _build_validator()

        result = validator.validate(_build_workspace("workspace-1", preset_ids=("preset-does-not-exist",)))

        assert result.valid is False
        assert any(v.code == "UNKNOWN_PRESET" for v in result.violations)

    def test_unknown_group(self):
        validator = _build_validator()

        result = validator.validate(_build_workspace("workspace-1", group_ids=("group-does-not-exist",)))

        assert result.valid is False
        assert any(v.code == "UNKNOWN_GROUP" for v in result.violations)


class TestDuplicateResourceReferences:
    def test_duplicate_bindings(self):
        validator = _build_validator()

        malformed = SimpleNamespace(
            workspace_id="workspace-1",
            name="Workspace",
            binding_ids=("binding-a", "binding-a"),
            template_ids=(),
            preset_ids=(),
            group_ids=(),
        )

        result = validator.validate(malformed)

        assert result.valid is False
        assert any(v.code == "DUPLICATE_MEMBER" for v in result.violations)


class TestRegistryValidation:
    def test_valid_registry(self):
        validator = _build_validator()

        registry_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceRegistryService()
        registry_service.register(_build_workspace("workspace-1", binding_ids=("binding-a",)))
        registry_service.register(_build_workspace("workspace-2", preset_ids=("preset-a",)))

        result = validator.validate_registry(registry_service._registry)

        assert result.valid is True
        assert result.violations == ()

    def test_none_registry(self):
        validator = _build_validator()

        result = validator.validate_registry(None)

        assert result.valid is False
        assert any(v.code == "MISSING_REGISTRY" for v in result.violations)

    def test_registry_with_unknown_resource(self):
        validator = _build_validator()

        malformed_registry = SimpleNamespace(
            workspaces={
                "workspace-1": SimpleNamespace(
                    workspace_id="workspace-1",
                    name="Workspace",
                    binding_ids=("binding-does-not-exist",),
                    template_ids=(),
                    preset_ids=(),
                    group_ids=(),
                )
            }
        )

        result = validator.validate_registry(malformed_registry)

        assert result.valid is False
        assert any(v.code == "UNKNOWN_BINDING" for v in result.violations)


class TestSnapshotValidation:
    def test_valid_snapshot(self):
        validator = _build_validator()

        snapshot = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSnapshot(
            workspace_id="workspace-1",
            created_at=datetime.now(timezone.utc),
            resource_counts={"bindings": 1, "templates": 0, "presets": 0, "groups": 0},
        )

        result = validator.validate_snapshot(snapshot)

        assert result.valid is True
        assert result.violations == ()

    def test_none_snapshot(self):
        validator = _build_validator()

        result = validator.validate_snapshot(None)

        assert result.valid is False
        assert any(v.code == "MISSING_SNAPSHOT" for v in result.violations)

    def test_missing_snapshot_workspace_id(self):
        validator = _build_validator()

        malformed = SimpleNamespace(
            workspace_id="   ",
            created_at=datetime.now(timezone.utc),
            resource_counts={"bindings": 0, "templates": 0, "presets": 0, "groups": 0},
        )

        result = validator.validate_snapshot(malformed)

        assert result.valid is False
        assert any(v.code == "MISSING_SNAPSHOT_WORKSPACE_ID" for v in result.violations)

    def test_missing_snapshot_created_at(self):
        validator = _build_validator()

        malformed = SimpleNamespace(
            workspace_id="workspace-1",
            created_at=None,
            resource_counts={"bindings": 0, "templates": 0, "presets": 0, "groups": 0},
        )

        result = validator.validate_snapshot(malformed)

        assert result.valid is False
        assert any(v.code == "MISSING_SNAPSHOT_CREATED_AT" for v in result.violations)

    def test_invalid_resource_counts_keys(self):
        validator = _build_validator()

        malformed = SimpleNamespace(
            workspace_id="workspace-1",
            created_at=datetime.now(timezone.utc),
            resource_counts={"bindings": 0},
        )

        result = validator.validate_snapshot(malformed)

        assert result.valid is False
        assert any(v.code == "INVALID_RESOURCE_COUNTS" for v in result.violations)

    def test_invalid_resource_count_value(self):
        validator = _build_validator()

        malformed = SimpleNamespace(
            workspace_id="workspace-1",
            created_at=datetime.now(timezone.utc),
            resource_counts={"bindings": -1, "templates": 0, "presets": 0, "groups": 0},
        )

        result = validator.validate_snapshot(malformed)

        assert result.valid is False
        assert any(v.code == "INVALID_RESOURCE_COUNT" for v in result.violations)


class TestMultipleViolations:
    def test_multiple_violations(self):
        validator = _build_validator()

        malformed = SimpleNamespace(
            workspace_id=None,
            name=None,
            binding_ids=("binding-does-not-exist",),
            template_ids=(),
            preset_ids=(),
            group_ids=(),
        )

        result = validator.validate(malformed)

        assert result.valid is False

        codes = {v.code for v in result.violations}

        assert "MISSING_WORKSPACE_ID" in codes
        assert "MISSING_WORKSPACE_NAME" in codes
        assert "UNKNOWN_BINDING" in codes
        assert len(result.violations) >= 3


class TestImmutableValidationResult:
    def test_immutable_result(self):
        validator = _build_validator()

        result = validator.validate(_build_workspace("workspace-1", binding_ids=("binding-a",)))

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.valid = False

    def test_immutable_violations(self):
        validator = _build_validator()

        malformed = SimpleNamespace(
            workspace_id="   ",
            name="Workspace",
            binding_ids=(),
            template_ids=(),
            preset_ids=(),
            group_ids=(),
        )

        result = validator.validate(malformed)

        with pytest.raises(dataclasses.FrozenInstanceError):
            result.violations[0].code = "CHANGED"

    def test_does_not_mutate_input(self):
        validator = _build_validator()

        malformed = SimpleNamespace(
            workspace_id="   ",
            name="Workspace",
            binding_ids=(),
            template_ids=(),
            preset_ids=(),
            group_ids=(),
        )

        validator.validate(malformed)

        assert malformed.workspace_id == "   "
