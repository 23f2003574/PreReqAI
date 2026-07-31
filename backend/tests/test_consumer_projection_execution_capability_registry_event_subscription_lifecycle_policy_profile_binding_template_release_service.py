import dataclasses

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplate,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateParameterizationService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRelease,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateReleaseError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateReleaseResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateReleaseService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateReleaseStatus,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersionService,
)


def _template(template_id, binding_ids=()):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplate(
        template_id=template_id,
        name=template_id,
        binding_ids=binding_ids,
        metadata={},
    )


def _build_context(template_id="template-1"):
    template_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRegistryService()
    template_registry.register(_template(template_id, binding_ids=("binding-1",)))

    parameterization_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateParameterizationService(
        template_registry,
        {},
    )

    template_version_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateVersionService(
        template_registry,
        parameterization_service,
    )

    release_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateReleaseService(
        template_registry,
        template_version_service,
    )

    return {
        "release_service": release_service,
        "template_registry": template_registry,
        "template_version_service": template_version_service,
        "template_id": template_id,
    }


def _publish(context, version):
    context["template_version_service"].publish(context["template_id"], version)


class TestReleaseVersion:
    def test_release_version(self):
        context = _build_context()
        _publish(context, "1.0.0")

        result = context["release_service"].release(context["template_id"], "1.0.0")

        assert isinstance(result, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateReleaseResult)
        assert result.previous_status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateReleaseStatus.DRAFT
        assert result.current_status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateReleaseStatus.RELEASED
        assert isinstance(result.release, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateRelease)
        assert result.release.template_id == context["template_id"]
        assert result.release.version == "1.0.0"


class TestRetireVersion:
    def test_retire_version(self):
        context = _build_context()
        _publish(context, "1.0.0")

        context["release_service"].release(context["template_id"], "1.0.0")
        result = context["release_service"].retire(context["template_id"], "1.0.0")

        assert result.previous_status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateReleaseStatus.RELEASED
        assert result.current_status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateReleaseStatus.RETIRED
        assert context["release_service"].is_released(context["template_id"], "1.0.0") is False


class TestLatestReleaseLookup:
    def test_latest_release_lookup(self):
        context = _build_context()
        _publish(context, "1.0.0")

        context["template_registry"].replace(
            _template(context["template_id"], binding_ids=("binding-1", "binding-2"))
        )
        _publish(context, "2.0.0")

        assert context["release_service"].latest_release(context["template_id"]) is None

        context["release_service"].release(context["template_id"], "1.0.0")
        latest = context["release_service"].release(context["template_id"], "2.0.0")

        assert context["release_service"].latest_release(context["template_id"]) == latest.release

        context["release_service"].retire(context["template_id"], "2.0.0")

        assert context["release_service"].latest_release(context["template_id"]).version == "1.0.0"


class TestIsReleasedTrueFalse:
    def test_is_released_true_and_false(self):
        context = _build_context()
        _publish(context, "1.0.0")

        assert context["release_service"].is_released(context["template_id"], "1.0.0") is False

        context["release_service"].release(context["template_id"], "1.0.0")

        assert context["release_service"].is_released(context["template_id"], "1.0.0") is True


class TestDuplicateReleaseRejection:
    def test_reject_duplicate_release(self):
        context = _build_context()
        _publish(context, "1.0.0")

        context["release_service"].release(context["template_id"], "1.0.0")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateReleaseError):
            context["release_service"].release(context["template_id"], "1.0.0")


class TestInvalidTransitionRejection:
    def test_reject_retiring_non_released_version(self):
        context = _build_context()
        _publish(context, "1.0.0")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateReleaseError):
            context["release_service"].retire(context["template_id"], "1.0.0")

    def test_reject_re_releasing_retired_version(self):
        context = _build_context()
        _publish(context, "1.0.0")

        context["release_service"].release(context["template_id"], "1.0.0")
        context["release_service"].retire(context["template_id"], "1.0.0")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateReleaseError):
            context["release_service"].release(context["template_id"], "1.0.0")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateReleaseError):
            context["release_service"].retire(context["template_id"], "1.0.0")

    def test_reject_unknown_template(self):
        context = _build_context()
        _publish(context, "1.0.0")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateReleaseError):
            context["release_service"].release("template-missing", "1.0.0")

    def test_reject_unknown_version(self):
        context = _build_context()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateReleaseError):
            context["release_service"].release(context["template_id"], "does-not-exist")

    def test_reject_blank_ids(self):
        context = _build_context()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateReleaseError):
            context["release_service"].release("   ", "1.0.0")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateReleaseError):
            context["release_service"].release(context["template_id"], None)


class TestImmutableReleaseHistory:
    def test_immutable_release_history(self):
        context = _build_context()
        _publish(context, "1.0.0")

        released = context["release_service"].release(context["template_id"], "1.0.0").release

        with pytest.raises(dataclasses.FrozenInstanceError):
            released.status = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateReleaseStatus.RETIRED

        retired_result = context["release_service"].retire(context["template_id"], "1.0.0")

        assert released.status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateReleaseStatus.RELEASED
        assert retired_result.release.status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateReleaseStatus.RETIRED
        assert retired_result.release.release_id == released.release_id


class TestDeploymentAllowedOnlyForReleasedVersions:
    def test_deployment_gate_reflects_release_status(self):
        context = _build_context()
        _publish(context, "1.0.0")

        def deployable(template_id, version):
            return context["release_service"].is_released(template_id, version)

        assert deployable(context["template_id"], "1.0.0") is False

        context["release_service"].release(context["template_id"], "1.0.0")
        assert deployable(context["template_id"], "1.0.0") is True

        context["release_service"].retire(context["template_id"], "1.0.0")
        assert deployable(context["template_id"], "1.0.0") is False


class TestRejectNoneDependencies:
    def test_reject_none_dependencies(self):
        context = _build_context()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateReleaseError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateReleaseService(
                None, context["template_version_service"]
            )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateReleaseError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingTemplateReleaseService(
                context["template_registry"], None
            )
