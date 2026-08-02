import dataclasses

from datetime import (
    datetime,
    timezone,
)

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBinding,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspace,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceParameter,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceParameterizationError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceParameterizationService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceParameterValues,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSnapshot,
)


def _binding(binding_id):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBinding(
        binding_id=binding_id,
        profile_id="development",
        capability_id=f"capability-{binding_id}",
        created_at=datetime.now(timezone.utc),
    )


def _parameter(name, type_=str, required=False, default_value=None):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceParameter(
        name=name,
        type=type_,
        required=required,
        default_value=default_value,
    )


def _values(**values):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceParameterValues(
        values=values,
    )


def _build_context(binding_ids=("binding-1", "binding-2"), parameter_definitions=None):
    binding_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingRegistryService()
    for binding_id in binding_ids:
        binding_service.register(_binding(binding_id))

    template_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryService()
    preset_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingPresetRegistryService()
    group_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryService()

    workspace_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceService(
        binding_service, template_service, preset_service, group_service
    )

    workspace_service.create(
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspace(
            workspace_id="workspace-1",
            name="Workspace One",
            description="A workspace.",
            binding_ids=binding_ids,
            template_ids=(),
            preset_ids=(),
            group_ids=(),
        )
    )

    parameterization_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceParameterizationService(
        workspace_service,
        parameter_definitions or {},
    )

    return parameterization_service, workspace_service


class TestApplyWithDefaults:
    def test_apply_with_defaults(self):
        service, _ = _build_context(
            parameter_definitions={"workspace-1": (_parameter("retry_limit", type_=int, default_value=3),)},
        )

        merged = service.validate("workspace-1", _values())

        assert isinstance(merged, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceParameterValues)
        assert dict(merged.values) == {"retry_limit": 3}
        assert dict(service.defaults("workspace-1").values) == {"retry_limit": 3}

        snapshot = service.apply("workspace-1", _values())

        assert isinstance(snapshot, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSnapshot)
        assert snapshot.workspace_id == "workspace-1"
        assert snapshot.resource_counts["bindings"] == 2


class TestOverrideDefaults:
    def test_override_defaults(self):
        service, _ = _build_context(
            parameter_definitions={"workspace-1": (_parameter("retry_limit", type_=int, default_value=3),)},
        )

        merged = service.validate("workspace-1", _values(retry_limit=7))

        assert dict(merged.values) == {"retry_limit": 7}


class TestRequiredParameterValidation:
    def test_required_parameter_validation(self):
        service, _ = _build_context(
            parameter_definitions={"workspace-1": (_parameter("region", required=True),)},
        )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceParameterizationError):
            service.validate("workspace-1", _values())

        merged = service.validate("workspace-1", _values(region="us-east-1"))

        assert dict(merged.values) == {"region": "us-east-1"}


class TestInvalidTypeRejection:
    def test_invalid_type_rejection(self):
        service, _ = _build_context(
            parameter_definitions={"workspace-1": (_parameter("retry_limit", type_=int),)},
        )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceParameterizationError):
            service.validate("workspace-1", _values(retry_limit="not-an-int"))


class TestUnknownParameterRejection:
    def test_unknown_parameter_rejection(self):
        service, _ = _build_context(
            parameter_definitions={"workspace-1": (_parameter("retry_limit", type_=int),)},
        )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceParameterizationError):
            service.validate("workspace-1", _values(unexpected="value"))


class TestDuplicateParameterRejection:
    def test_duplicate_parameter_rejection(self):
        service, _ = _build_context(
            parameter_definitions={
                "workspace-1": (_parameter("retry_limit"), _parameter("retry_limit")),
            },
        )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceParameterizationError):
            service.validate("workspace-1", _values())

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceParameterizationError):
            service.defaults("workspace-1")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceParameterizationError):
            service.supported_parameters("workspace-1")


class TestSupportedParameters:
    def test_supported_parameters(self):
        parameters = (_parameter("retry_limit", type_=int, default_value=3),)
        service, _ = _build_context(parameter_definitions={"workspace-1": parameters})

        assert service.supported_parameters("workspace-1") == parameters

    def test_undeclared_workspace_has_no_parameters(self):
        service, _ = _build_context()

        assert service.supported_parameters("workspace-1") == ()


class TestImmutableConfiguredWorkspace:
    def test_immutable_configured_workspace_snapshot(self):
        service, _ = _build_context(
            parameter_definitions={"workspace-1": (_parameter("retry_limit", type_=int, default_value=3),)},
        )

        snapshot = service.apply("workspace-1", _values())

        with pytest.raises(dataclasses.FrozenInstanceError):
            snapshot.workspace_id = "changed"

    def test_immutable_parameter_values(self):
        service, _ = _build_context(
            parameter_definitions={"workspace-1": (_parameter("retry_limit", type_=int, default_value=3),)},
        )

        merged = service.validate("workspace-1", _values())

        with pytest.raises(dataclasses.FrozenInstanceError):
            merged.values = {}


class TestRejectInvalidInputs:
    def test_reject_none_dependencies(self):
        _, workspace_service = _build_context()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceParameterizationError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceParameterizationService(None, {})

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceParameterizationError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceParameterizationService(workspace_service, None)

    def test_reject_blank_workspace_id(self):
        service, _ = _build_context()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceParameterizationError):
            service.validate("   ", _values())

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceParameterizationError):
            service.defaults(None)

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceParameterizationError):
            service.supported_parameters("")

    def test_reject_none_values(self):
        service, _ = _build_context(
            parameter_definitions={"workspace-1": ()},
        )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceParameterizationError):
            service.validate("workspace-1", None)
