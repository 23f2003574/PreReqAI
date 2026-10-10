import dataclasses

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRelease,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateReleaseError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateReleaseResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateReleaseService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateReleaseStatus,
)


_STATUS = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateReleaseStatus


class TestReleaseVersion:
    """A never-released version can be released, promoting DRAFT to RELEASED."""

    def test_release_version(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateReleaseService()

        result = service.release(
            "standard-registration",

            "1.0.0",
        )

        assert isinstance(
            result,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateReleaseResult,
        )
        assert result.previous_status == _STATUS.DRAFT
        assert result.current_status == _STATUS.RELEASED
        assert isinstance(
            result.release,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRelease,
        )
        assert result.release.template_id == "standard-registration"
        assert result.release.version == "1.0.0"
        assert result.release.released_at is not None


class TestRetireVersion:
    """A released version can be retired, demoting RELEASED to RETIRED."""

    def test_retire_version(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateReleaseService()
        release_result = service.release(
            "standard-registration",

            "1.0.0",
        )

        retire_result = service.retire(
            "standard-registration",

            "1.0.0",
        )

        assert retire_result.previous_status == _STATUS.RELEASED
        assert retire_result.current_status == _STATUS.RETIRED
        assert retire_result.release.released_at == release_result.release.released_at
        assert retire_result.release is not release_result.release


class TestLatestReleaseLookup:
    """latest_release() returns the currently active release for a template."""

    def test_latest_release_lookup(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateReleaseService()
        service.release(
            "standard-registration",

            "1.0.0",
        )
        service.retire(
            "standard-registration",

            "1.0.0",
        )
        service.release(
            "standard-registration",

            "1.1.0",
        )

        latest = service.latest_release(
            "standard-registration"
        )

        assert latest.version == "1.1.0"
        assert latest.status == _STATUS.RELEASED

    def test_latest_release_lookup_missing(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateReleaseService()

        assert service.latest_release("does-not-exist") is None

    def test_latest_release_lookup_all_retired(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateReleaseService()
        service.release(
            "standard-registration",

            "1.0.0",
        )
        service.retire(
            "standard-registration",

            "1.0.0",
        )

        assert service.latest_release("standard-registration") is None


class TestIsReleased:
    """is_released() reports current RELEASED status accurately."""

    def test_is_released_true(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateReleaseService()
        service.release(
            "standard-registration",

            "1.0.0",
        )

        assert service.is_released("standard-registration", "1.0.0") is True

    def test_is_released_false_never_released(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateReleaseService()

        assert service.is_released("standard-registration", "1.0.0") is False

    def test_is_released_false_retired(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateReleaseService()
        service.release(
            "standard-registration",

            "1.0.0",
        )
        service.retire(
            "standard-registration",

            "1.0.0",
        )

        assert service.is_released("standard-registration", "1.0.0") is False


class TestRejectDuplicateRelease:
    """Releasing an already-released version is rejected."""

    def test_reject_duplicate_release(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateReleaseService()
        service.release(
            "standard-registration",

            "1.0.0",
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateReleaseError
        ):
            service.release(
                "standard-registration",

                "1.0.0",
            )


class TestRejectInvalidTransitions:
    """Retiring a non-released version and re-releasing a retired one are rejected."""

    def test_reject_retiring_never_released_version(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateReleaseService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateReleaseError
        ):
            service.retire(
                "standard-registration",

                "1.0.0",
            )

    def test_reject_retiring_already_retired_version(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateReleaseService()
        service.release(
            "standard-registration",

            "1.0.0",
        )
        service.retire(
            "standard-registration",

            "1.0.0",
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateReleaseError
        ):
            service.retire(
                "standard-registration",

                "1.0.0",
            )

    def test_reject_releasing_retired_version(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateReleaseService()
        service.release(
            "standard-registration",

            "1.0.0",
        )
        service.retire(
            "standard-registration",

            "1.0.0",
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateReleaseError
        ):
            service.release(
                "standard-registration",

                "1.0.0",
            )

    def test_reject_none_inputs(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateReleaseService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateReleaseError
        ):
            service.release(
                None,

                "1.0.0",
            )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateReleaseError
        ):
            service.release(
                "standard-registration",

                None,
            )

    def test_reject_missing_template_or_version(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateReleaseService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateReleaseError
        ):
            service.release(
                "   ",

                "1.0.0",
            )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateReleaseError
        ):
            service.release(
                "standard-registration",

                "   ",
            )


class TestImmutableReleaseHistory:
    """Transitions never mutate a prior release record; they produce a new one."""

    def test_immutable_release_history(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateReleaseService()

        release_result = service.release(
            "standard-registration",

            "1.0.0",
        )
        original_release = release_result.release

        service.retire(
            "standard-registration",

            "1.0.0",
        )

        assert original_release.status == _STATUS.RELEASED

        with pytest.raises(dataclasses.FrozenInstanceError):
            original_release.status = _STATUS.RETIRED

        with pytest.raises(dataclasses.FrozenInstanceError):
            release_result.current_status = _STATUS.RETIRED
