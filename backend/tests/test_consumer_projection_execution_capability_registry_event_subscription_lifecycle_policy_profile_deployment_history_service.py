import dataclasses

from datetime import datetime, timezone

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentHistoryError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentHistoryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentRecord,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentStatus,
)


def _build_record(deployment_id, profile_id="development", version="1.0.0", target_environment="production", deployment_status=None):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentRecord(
        deployment_id=deployment_id,

        profile_id=profile_id,

        version=version,

        target_environment=target_environment,

        deployed_at=datetime.now(timezone.utc),

        deployment_status=(
            deployment_status
            if deployment_status is not None
            else ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentStatus.SUCCEEDED
        ),
    )


class TestRecordDeployment:
    """A single deployment can be recorded and later found."""

    def test_record_deployment(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentHistoryService()
        record = _build_record("deployment-1")

        service.record(record)

        assert service.find("deployment-1") is record


class TestLookupDeployment:
    """find() distinguishes recorded and unrecorded deployment IDs."""

    def test_find_existing(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentHistoryService()
        record = _build_record("deployment-1")
        service.record(record)

        assert service.find("deployment-1") is record

    def test_find_missing(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentHistoryService()

        assert service.find("does-not-exist") is None


class TestListDeployments:
    """list() returns every recorded deployment."""

    def test_list_deployments(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentHistoryService()
        first = _build_record("deployment-1")
        second = _build_record("deployment-2")
        service.record(first)
        service.record(second)

        assert service.list() == (first, second)


class TestProfileHistory:
    """history() filters recorded deployments by profile ID."""

    def test_profile_history(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentHistoryService()
        first = _build_record(
            "deployment-1",

            profile_id="development",
        )
        second = _build_record(
            "deployment-2",

            profile_id="staging-profile",
        )
        third = _build_record(
            "deployment-3",

            profile_id="development",
        )
        service.record(first)
        service.record(second)
        service.record(third)

        assert service.history("development") == (first, third)
        assert service.history("staging-profile") == (second,)
        assert service.history("does-not-exist") == ()


class TestEnvironmentHistory:
    """history_for_environment() filters recorded deployments by target environment."""

    def test_environment_history(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentHistoryService()
        first = _build_record(
            "deployment-1",

            target_environment="production",
        )
        second = _build_record(
            "deployment-2",

            target_environment="staging",
        )
        third = _build_record(
            "deployment-3",

            target_environment="production",
        )
        service.record(first)
        service.record(second)
        service.record(third)

        assert service.history_for_environment("production") == (first, third)
        assert service.history_for_environment("staging") == (second,)
        assert service.history_for_environment("does-not-exist") == ()


class TestChronologicalOrdering:
    """Deployments are listed in chronological (recording) order."""

    def test_chronological_ordering(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentHistoryService()
        first = _build_record("deployment-1")
        second = _build_record("deployment-2")
        third = _build_record("deployment-3")
        service.record(first)
        service.record(second)
        service.record(third)

        assert service.list() == (first, second, third)


class TestImmutableHistory:
    """A previously listed snapshot is unaffected by later recordings."""

    def test_immutable_history(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentHistoryService()
        service.record(
            _build_record("deployment-1")
        )

        snapshot = service.list()

        service.record(
            _build_record("deployment-2")
        )

        assert len(snapshot) == 1
        assert len(service.list()) == 2

        with pytest.raises(dataclasses.FrozenInstanceError):
            snapshot[0].deployment_id = "changed"


class TestRejectDuplicateDeploymentIds:
    """Recording a second deployment with the same ID is rejected."""

    def test_reject_duplicate_deployment_ids(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentHistoryService()
        service.record(
            _build_record("deployment-1")
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentHistoryError
        ):
            service.record(
                _build_record("deployment-1")
            )

        assert len(service.list()) == 1


class TestRejectInvalidInputs:
    """None records, blank identifiers, and unknown deployment statuses are rejected."""

    def test_reject_none_record(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentHistoryService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentHistoryError
        ):
            service.record(None)

    def test_reject_blank_deployment_id(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentHistoryService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentHistoryError
        ):
            service.record(
                _build_record("   ")
            )

    def test_reject_blank_profile_id(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentHistoryService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentHistoryError
        ):
            service.record(
                _build_record(
                    "deployment-1",

                    profile_id="   ",
                )
            )

    def test_reject_blank_target_environment(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentHistoryService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentHistoryError
        ):
            service.record(
                _build_record(
                    "deployment-1",

                    target_environment="   ",
                )
            )

    def test_reject_invalid_deployment_status(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentHistoryService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentHistoryError
        ):
            service.record(
                _build_record(
                    "deployment-1",

                    deployment_status="not-a-real-status",
                )
            )

    def test_reject_wrong_type(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentHistoryService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentHistoryError
        ):
            service.record("not-a-record")
