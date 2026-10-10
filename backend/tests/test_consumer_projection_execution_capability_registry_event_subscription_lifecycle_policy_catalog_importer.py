import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalog,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogExport,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogExporter,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogImportError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogImportResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogImporter,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogMetadata,
)


def _build_policy(initial_state):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyBuilder().build(
        (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.REGISTERED,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.ACTIVE,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.SUSPENDED,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.UNREGISTERED,
        ),
        initial_state,
    )


def _build_metadata():
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogMetadata(
        catalog_name="core-lifecycle-policies",

        catalog_version="1.0.0",

        description="Core lifecycle policy catalog.",
    )


def _export_of(policies):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogExport(
        metadata=_build_metadata(),

        policies=policies,
    )


class TestImportEmptyCatalog:
    """An empty exported catalog can be imported."""

    def test_import_empty_catalog(self):
        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogImporter().import_catalog(
            _export_of({})
        )

        assert isinstance(
            result,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogImportResult,
        )
        assert isinstance(
            result.catalog,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalog,
        )
        assert result.imported_policy_count == 0


class TestImportPopulatedCatalog:
    """A populated exported catalog can be imported."""

    def test_import_populated_catalog(self):
        policy = _build_policy(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.REGISTERED,
        )

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogImporter().import_catalog(
            _export_of(
                {
                    "registered-default": policy,
                }
            )
        )

        assert result.catalog.policies["registered-default"] is policy


class TestImportedCountCorrect:
    """The import result's policy count matches the number of imported policies."""

    def test_imported_count_correct(self):
        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogImporter().import_catalog(
            _export_of(
                {
                    "registered-default": _build_policy(
                        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.REGISTERED,
                    ),

                    "active-default": _build_policy(
                        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.ACTIVE,
                    ),
                }
            )
        )

        assert result.imported_policy_count == 2


class TestImportPreservesMetadata:
    """Importing preserves the export's metadata on the rebuilt catalog."""

    def test_import_preserves_metadata(self):
        metadata = _build_metadata()

        export = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogExport(
            metadata=metadata,

            policies={},
        )

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogImporter().import_catalog(
            export
        )

        assert result.catalog.metadata is metadata


class TestImportRoundTrip:
    """A catalog exported then imported preserves ordering."""

    def test_import_round_trip(self):
        original = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogBuilder().build(
            _build_metadata(),

            [
                (
                    "zeta",
                    _build_policy(
                        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.REGISTERED,
                    ),
                ),
                (
                    "alpha",
                    _build_policy(
                        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.ACTIVE,
                    ),
                ),
            ],
        )

        export = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogExporter().export(
            original
        )

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogImporter().import_catalog(
            export
        )

        assert list(result.catalog.policies.keys()) == [
            "zeta",
            "alpha",
        ]


class TestRejectNoneExport:
    """A None export is rejected."""

    def test_reject_none_export(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogImportError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogImporter().import_catalog(
                None
            )


class TestRejectInvalidExportStructure:
    """An export with a non-iterable policies structure is rejected."""

    def test_reject_invalid_export_structure(self):
        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogImportError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogImporter().import_catalog(
                _export_of(42)
            )


class TestRejectMissingMetadata:
    """An export with missing metadata is rejected."""

    def test_reject_missing_metadata(self):
        export = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogExport(
            metadata=None,

            policies={},
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogImportError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogImporter().import_catalog(
                export
            )


class TestRejectDuplicateIdentifiers:
    """An export whose policies contain duplicate identifiers is rejected."""

    def test_reject_duplicate_identifiers(self):
        export = _export_of(
            [
                (
                    "duplicate",
                    _build_policy(
                        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.REGISTERED,
                    ),
                ),
                (
                    "duplicate",
                    _build_policy(
                        ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.ACTIVE,
                    ),
                ),
            ]
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogImportError
        ):
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyCatalogImporter().import_catalog(
                export
            )
