import dataclasses

from datetime import datetime, timezone

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentHistoryError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentHistoryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentRecord,
)


def _build_record(deployment_id, template_id="standard-registration", template_version="1.0.0", target_registry="production"):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentRecord(
        deployment_id=deployment_id,

        template_id=template_id,

        template_version=template_version,

        target_registry=target_registry,

        deployed_at=datetime.now(timezone.utc),
    )


class TestRecordDeployment:
    """A single deployment can be recorded and later found."""

    def test_record_deployment(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentHistoryService()
        record = _build_record("deployment-1")

        service.record(record)

        assert service.find("deployment-1") is record


class TestFindExistingAndMissing:
    """find() distinguishes recorded and unrecorded deployment IDs."""

    def test_find_existing(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentHistoryService()
        record = _build_record("deployment-1")
        service.record(record)

        assert service.find("deployment-1") is record

    def test_find_missing(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentHistoryService()

        assert service.find("does-not-exist") is None


class TestTemplateHistory:
    """history() filters recorded deployments by template ID."""

    def test_template_history(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentHistoryService()
        first = _build_record(
            "deployment-1",

            template_id="standard-registration",
        )
        second = _build_record(
            "deployment-2",

            template_id="premium-registration",
        )
        third = _build_record(
            "deployment-3",

            template_id="standard-registration",
        )
        service.record(first)
        service.record(second)
        service.record(third)

        assert service.history("standard-registration") == (first, third)
        assert service.history("premium-registration") == (second,)
        assert service.history("does-not-exist") == ()


class TestRegistryHistory:
    """history_for_registry() filters recorded deployments by target registry."""

    def test_registry_history(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentHistoryService()
        first = _build_record(
            "deployment-1",

            target_registry="production",
        )
        second = _build_record(
            "deployment-2",

            target_registry="staging",
        )
        third = _build_record(
            "deployment-3",

            target_registry="production",
        )
        service.record(first)
        service.record(second)
        service.record(third)

        assert service.history_for_registry("production") == (first, third)
        assert service.history_for_registry("staging") == (second,)
        assert service.history_for_registry("does-not-exist") == ()


class TestOrderingPreserved:
    """Deployments are listed in chronological (recording) order."""

    def test_ordering_preserved(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentHistoryService()
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
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentHistoryService()
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
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentHistoryService()
        service.record(
            _build_record("deployment-1")
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentHistoryError
        ):
            service.record(
                _build_record("deployment-1")
            )

        assert len(service.list()) == 1


class TestRejectNoneRecord:
    """Recording a None record is rejected."""

    def test_reject_none_record(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentHistoryService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentHistoryError
        ):
            service.record(None)


class TestRejectBlankIdentifiers:
    """Recording a record with a blank deployment ID or template ID is rejected."""

    def test_reject_blank_deployment_id(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentHistoryService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentHistoryError
        ):
            service.record(
                _build_record("   ")
            )

    def test_reject_blank_template_id(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentHistoryService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentHistoryError
        ):
            service.record(
                _build_record(
                    "deployment-1",

                    template_id="   ",
                )
            )

    def test_reject_wrong_type(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentHistoryService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentHistoryError
        ):
            service.record("not-a-record")
