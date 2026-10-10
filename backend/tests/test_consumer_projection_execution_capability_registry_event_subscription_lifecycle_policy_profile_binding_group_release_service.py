import dataclasses

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroup,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRelease,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupReleaseError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupReleaseResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupReleaseService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupReleaseStatus,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupVersionService,
)


def _build_context(group_id="group-1"):
    group_registry = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRegistryService()
    group_registry.register(
        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroup(
            group_id=group_id,
            group_name=group_id,
            binding_ids=("binding-1",),
        )
    )

    group_version_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupVersionService(
        group_registry
    )

    release_service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupReleaseService(
        group_registry,
        group_version_service,
    )

    return {
        "release_service": release_service,
        "group_registry": group_registry,
        "group_version_service": group_version_service,
        "group_id": group_id,
    }


def _publish(context, version):
    context["group_version_service"].publish(context["group_id"], version)


class TestReleaseVersion:
    def test_release_version(self):
        context = _build_context()
        _publish(context, "1.0.0")

        result = context["release_service"].release(context["group_id"], "1.0.0")

        assert isinstance(result, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupReleaseResult)
        assert result.previous_status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupReleaseStatus.DRAFT
        assert result.current_status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupReleaseStatus.RELEASED
        assert isinstance(result.release, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupRelease)
        assert result.release.group_id == context["group_id"]
        assert result.release.version == "1.0.0"


class TestRetireVersion:
    def test_retire_version(self):
        context = _build_context()
        _publish(context, "1.0.0")

        context["release_service"].release(context["group_id"], "1.0.0")
        result = context["release_service"].retire(context["group_id"], "1.0.0")

        assert result.previous_status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupReleaseStatus.RELEASED
        assert result.current_status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupReleaseStatus.RETIRED
        assert context["release_service"].is_released(context["group_id"], "1.0.0") is False


class TestLatestReleaseLookup:
    def test_latest_release_lookup(self):
        context = _build_context()
        _publish(context, "1.0.0")

        context["group_registry"].replace(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroup(
                group_id=context["group_id"],
                group_name=context["group_id"],
                binding_ids=("binding-1", "binding-2"),
            )
        )
        _publish(context, "2.0.0")

        assert context["release_service"].latest_release(context["group_id"]) is None

        context["release_service"].release(context["group_id"], "1.0.0")
        latest = context["release_service"].release(context["group_id"], "2.0.0")

        assert context["release_service"].latest_release(context["group_id"]) == latest.release

        context["release_service"].retire(context["group_id"], "2.0.0")

        assert context["release_service"].latest_release(context["group_id"]).version == "1.0.0"


class TestIsReleasedTrueFalse:
    def test_is_released_true_and_false(self):
        context = _build_context()
        _publish(context, "1.0.0")

        assert context["release_service"].is_released(context["group_id"], "1.0.0") is False

        context["release_service"].release(context["group_id"], "1.0.0")

        assert context["release_service"].is_released(context["group_id"], "1.0.0") is True


class TestDuplicateReleaseRejection:
    def test_reject_duplicate_release(self):
        context = _build_context()
        _publish(context, "1.0.0")

        context["release_service"].release(context["group_id"], "1.0.0")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupReleaseError):
            context["release_service"].release(context["group_id"], "1.0.0")


class TestInvalidTransitionRejection:
    def test_reject_retiring_non_released_version(self):
        context = _build_context()
        _publish(context, "1.0.0")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupReleaseError):
            context["release_service"].retire(context["group_id"], "1.0.0")

    def test_reject_re_releasing_retired_version(self):
        context = _build_context()
        _publish(context, "1.0.0")

        context["release_service"].release(context["group_id"], "1.0.0")
        context["release_service"].retire(context["group_id"], "1.0.0")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupReleaseError):
            context["release_service"].release(context["group_id"], "1.0.0")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupReleaseError):
            context["release_service"].retire(context["group_id"], "1.0.0")

    def test_reject_unknown_group(self):
        context = _build_context()
        _publish(context, "1.0.0")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupReleaseError):
            context["release_service"].release("group-missing", "1.0.0")

    def test_reject_unknown_version(self):
        context = _build_context()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupReleaseError):
            context["release_service"].release(context["group_id"], "does-not-exist")

    def test_reject_blank_ids(self):
        context = _build_context()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupReleaseError):
            context["release_service"].release("   ", "1.0.0")

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupReleaseError):
            context["release_service"].release(context["group_id"], None)


class TestImmutableReleaseHistory:
    def test_immutable_release_history(self):
        context = _build_context()
        _publish(context, "1.0.0")

        released = context["release_service"].release(context["group_id"], "1.0.0").release

        with pytest.raises(dataclasses.FrozenInstanceError):
            released.status = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupReleaseStatus.RETIRED

        retired_result = context["release_service"].retire(context["group_id"], "1.0.0")

        assert released.status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupReleaseStatus.RELEASED
        assert retired_result.release.status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupReleaseStatus.RETIRED
        assert retired_result.release.release_id == released.release_id


class TestDeploymentAllowedOnlyForReleasedVersions:
    def test_deployment_gate_reflects_release_status(self):
        context = _build_context()
        _publish(context, "1.0.0")

        def deployable(group_id, version):
            return context["release_service"].is_released(group_id, version)

        assert deployable(context["group_id"], "1.0.0") is False

        context["release_service"].release(context["group_id"], "1.0.0")
        assert deployable(context["group_id"], "1.0.0") is True

        context["release_service"].retire(context["group_id"], "1.0.0")
        assert deployable(context["group_id"], "1.0.0") is False


class TestRejectNoneDependencies:
    def test_reject_none_dependencies(self):
        context = _build_context()

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupReleaseError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupReleaseService(
                None, context["group_version_service"]
            )

        with pytest.raises(ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupReleaseError):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingGroupReleaseService(
                context["group_registry"], None
            )
