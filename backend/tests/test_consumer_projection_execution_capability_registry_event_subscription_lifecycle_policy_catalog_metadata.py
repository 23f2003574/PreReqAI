import dataclasses

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogMetadata,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogMetadataError,
)


class TestBuildValidMetadata:
    """Valid catalog metadata can be built."""

    def test_build_valid_metadata(self):
        metadata = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogMetadata(
            catalog_name="core-lifecycle-policies",

            catalog_version="1.0.0",

            description="Core lifecycle policy catalog.",
        )

        assert metadata.catalog_name == "core-lifecycle-policies"
        assert metadata.catalog_version == "1.0.0"
        assert metadata.description == "Core lifecycle policy catalog."


class TestRejectEmptyCatalogName:
    """An empty catalog name is rejected."""

    def test_reject_empty_catalog_name(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogMetadataError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogMetadata(
                catalog_name="",

                catalog_version="1.0.0",

                description="Core lifecycle policy catalog.",
            )


class TestRejectNoneCatalogName:
    """A None catalog name is rejected."""

    def test_reject_none_catalog_name(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogMetadataError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogMetadata(
                catalog_name=None,

                catalog_version="1.0.0",

                description="Core lifecycle policy catalog.",
            )


class TestRejectEmptyCatalogVersion:
    """An empty catalog version is rejected."""

    def test_reject_empty_catalog_version(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogMetadataError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogMetadata(
                catalog_name="core-lifecycle-policies",

                catalog_version="",

                description="Core lifecycle policy catalog.",
            )


class TestRejectNoneCatalogVersion:
    """A None catalog version is rejected."""

    def test_reject_none_catalog_version(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogMetadataError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogMetadata(
                catalog_name="core-lifecycle-policies",

                catalog_version=None,

                description="Core lifecycle policy catalog.",
            )


class TestImmutableMetadata:
    """Built catalog metadata cannot have its fields reassigned."""

    def test_immutable_metadata(self):
        metadata = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogMetadata(
            catalog_name="core-lifecycle-policies",

            catalog_version="1.0.0",

            description="Core lifecycle policy catalog.",
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            metadata.catalog_name = "renamed"
