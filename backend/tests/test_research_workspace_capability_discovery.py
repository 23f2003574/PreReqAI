"""
Tests for research workspace capability discovery.

Validates that:
- Capabilities are discoverable
- Lookup works with enum and string
- Unknown capabilities are handled cleanly
- Support checks respect enabled state
- Serialization is consumer-friendly
- Gateway exposes discovery methods
- Gateway and registry remain consistent
"""

import pytest

from backend.session import (
    ResearchWorkspaceCapability,
    ResearchWorkspaceCapabilityDescriptor,
    ResearchWorkspaceCapabilities,
)


class TestCapabilityEnum:
    """Test capability enum is well-formed."""

    def test_all_capabilities_have_string_values(self):
        """Verify each capability has a string value."""
        expected_capabilities = {
            "sessions",
            "discovery",
            "lineage",
            "comparison",
            "organization",
            "activity",
            "insights",
            "snapshots",
            "import",
            "integrity",
            "change_feed",
            "subscriptions",
        }

        actual_values = {
            cap.value
            for cap in ResearchWorkspaceCapability
        }

        assert expected_capabilities == actual_values

    def test_enum_is_string_backed(self):
        """Verify enum is string-backed."""
        capability = (
            ResearchWorkspaceCapability.SESSIONS
        )

        assert isinstance(capability, str)

        assert capability == "sessions"


class TestCapabilityDescriptor:
    """Test capability descriptor is properly formed."""

    def test_descriptor_is_frozen(self):
        """Verify descriptor is frozen (immutable)."""
        descriptor = (
            ResearchWorkspaceCapabilityDescriptor(

                capability=(
                    ResearchWorkspaceCapability
                    .SESSIONS
                ),

                description="Test",

                operations=(
                    "op1",
                    "op2",
                ),
            )
        )

        with pytest.raises(Exception):
            descriptor.description = (
                "Modified"
            )

    def test_descriptor_operations_are_tuple(self):
        """Verify operations are stored as tuple."""
        descriptor = (
            ResearchWorkspaceCapabilityDescriptor(

                capability=(
                    ResearchWorkspaceCapability
                    .LINEAGE
                ),

                description="Lineage ops",

                operations=(
                    "get_lineage",
                    "get_ancestors",
                ),
            )
        )

        assert isinstance(
            descriptor.operations,
            tuple,
        )

        assert len(
            descriptor.operations
        ) == 2

    def test_descriptor_defaults(self):
        """Verify descriptor has correct defaults."""
        descriptor = (
            ResearchWorkspaceCapabilityDescriptor(

                capability=(
                    ResearchWorkspaceCapability
                    .DISCOVERY
                ),

                description="Discovery",

                operations=(
                    "search",
                ),
            )
        )

        assert descriptor.version == "1.0"

        assert descriptor.enabled is True


class TestCapabilityDescriptorSerialization:
    """Test descriptor serialization produces consumer-friendly output."""

    def test_descriptor_to_dict_has_capability_not_name(
        self,
    ):
        """Verify serialized form uses 'capability' key."""
        descriptor = (
            ResearchWorkspaceCapabilityDescriptor(

                capability=(
                    ResearchWorkspaceCapability
                    .INTEGRITY
                ),

                description="Integrity",

                operations=(
                    "audit",
                    "repair",
                ),

                version="1.0",

                enabled=True,
            )
        )

        serialized = descriptor.to_dict()

        assert "capability" in serialized

        assert "name" not in serialized

    def test_descriptor_serialization_uses_string_values(
        self,
    ):
        """Verify capability is serialized as string."""
        descriptor = (
            ResearchWorkspaceCapabilityDescriptor(

                capability=(
                    ResearchWorkspaceCapability
                    .CHANGE_FEED
                ),

                description="Change feed",

                operations=(
                    "get_changes",
                ),
            )
        )

        serialized = descriptor.to_dict()

        assert (
            serialized["capability"]
            == "change_feed"
        )

        assert isinstance(
            serialized["capability"],
            str,
        )

    def test_descriptor_serialization_produces_primitives(
        self,
    ):
        """Verify all serialized values are primitives."""
        descriptor = (
            ResearchWorkspaceCapabilityDescriptor(

                capability=(
                    ResearchWorkspaceCapability
                    .SNAPSHOTS
                ),

                description="Snapshots",

                operations=(
                    "export",
                    "import",
                ),

                version="2.0",

                enabled=False,
            )
        )

        serialized = descriptor.to_dict()

        assert isinstance(
            serialized["capability"],
            str,
        )

        assert isinstance(
            serialized["description"],
            str,
        )

        assert isinstance(
            serialized["operations"],
            list,
        )

        assert all(
            isinstance(op, str)
            for op in serialized["operations"]
        )

        assert isinstance(
            serialized["version"],
            str,
        )

        assert isinstance(
            serialized["enabled"],
            bool,
        )

    def test_descriptor_operations_serialized_as_list(
        self,
    ):
        """Verify operations tuple is serialized as list."""
        descriptor = (
            ResearchWorkspaceCapabilityDescriptor(

                capability=(
                    ResearchWorkspaceCapability
                    .ORGANIZATION
                ),

                description="Organization",

                operations=(
                    "tag",
                    "collection",
                ),
            )
        )

        serialized = descriptor.to_dict()

        operations = (
            serialized["operations"]
        )

        assert isinstance(
            operations,
            list,
        )

        assert (
            operations
            == ["tag", "collection"]
        )


class TestCapabilityRegistry:
    """Test capability registry functionality."""

    def test_default_capabilities_are_discoverable(
        self,
    ):
        """Verify registry lists expected capabilities."""
        registry = (
            ResearchWorkspaceCapabilities()
        )

        capabilities = (
            registry.list_capabilities()
        )

        assert len(capabilities) == 12

        capability_ids = {
            cap.capability.value
            for cap in capabilities
        }

        expected_ids = {
            "sessions",
            "discovery",
            "lineage",
            "comparison",
            "organization",
            "activity",
            "insights",
            "snapshots",
            "import",
            "integrity",
            "change_feed",
            "subscriptions",
        }

        assert capability_ids == expected_ids

    def test_all_default_capabilities_enabled(
        self,
    ):
        """Verify all default capabilities are enabled."""
        registry = (
            ResearchWorkspaceCapabilities()
        )

        capabilities = (
            registry.list_capabilities()
        )

        for cap in capabilities:
            assert cap.enabled is True

    def test_capability_lookup_by_enum(self):
        """Verify capability lookup works with enum."""
        registry = (
            ResearchWorkspaceCapabilities()
        )

        capability = (
            registry.get_capability(

                ResearchWorkspaceCapability
                .LINEAGE
            )
        )

        assert capability is not None

        assert (
            capability.capability
            == ResearchWorkspaceCapability
            .LINEAGE
        )

        assert (
            "get_lineage"
            in capability.operations
        )

    def test_capability_lookup_by_string(self):
        """Verify capability lookup works with string."""
        registry = (
            ResearchWorkspaceCapabilities()
        )

        capability = (
            registry.get_capability(
                "lineage"
            )
        )

        assert capability is not None

        assert (
            capability.capability.value
            == "lineage"
        )

    def test_unknown_capability_returns_none(
        self,
    ):
        """Verify unknown capability returns None."""
        registry = (
            ResearchWorkspaceCapabilities()
        )

        capability = (
            registry.get_capability(
                "does_not_exist"
            )
        )

        assert capability is None

    def test_supports_known_enabled_capability(
        self,
    ):
        """Verify supports() returns True for enabled."""
        registry = (
            ResearchWorkspaceCapabilities()
        )

        assert (
            registry.supports(
                "integrity"
            )
        ) is True

        assert (
            registry.supports(

                ResearchWorkspaceCapability
                .INTEGRITY
            )
        ) is True

    def test_supports_unknown_capability(self):
        """Verify supports() returns False for unknown."""
        registry = (
            ResearchWorkspaceCapabilities()
        )

        assert (
            registry.supports(
                "unknown"
            )
        ) is False

    def test_supports_disabled_capability(self):
        """Verify supports() returns False for disabled."""
        registry = (
            ResearchWorkspaceCapabilities()
        )

        # Create a custom registry with disabled
        registry._capabilities[
            "custom"
        ] = (
            ResearchWorkspaceCapabilityDescriptor(

                capability=(
                    ResearchWorkspaceCapability
                    .SESSIONS
                ),

                description="Disabled test",

                operations=("op",),

                enabled=False,
            )
        )

        assert (
            registry.supports(
                "custom"
            )
        ) is False

    def test_registry_serialization(self):
        """Verify registry serialization."""
        registry = (
            ResearchWorkspaceCapabilities()
        )

        serialized = registry.to_dict()

        assert "capabilities" in serialized

        capabilities = (
            serialized["capabilities"]
        )

        assert isinstance(
            capabilities,
            list,
        )

        assert len(capabilities) == 12

        for cap_dict in capabilities:
            assert "capability" in cap_dict

            assert (
                "description" in cap_dict
            )

            assert "operations" in cap_dict

            assert "version" in cap_dict

            assert "enabled" in cap_dict

            assert isinstance(
                cap_dict["capability"],
                str,
            )

    def test_descriptor_contains_expected_operations(
        self,
    ):
        """Verify operations list includes public ops."""
        registry = (
            ResearchWorkspaceCapabilities()
        )

        # Verify INTEGRITY ops
        integrity = (
            registry.get_capability(
                "integrity"
            )
        )

        assert (
            "audit_workspace"
            in integrity.operations
        )

        assert (
            "plan_repairs"
            in integrity.operations
        )

        # Verify SESSIONS ops
        sessions = (
            registry.get_capability(
                "sessions"
            )
        )

        assert (
            "create_session"
            in sessions.operations
        )

        assert (
            "get_session"
            in sessions.operations
        )

        # Verify CHANGE_FEED ops
        change_feed = (
            registry.get_capability(
                "change_feed"
            )
        )

        assert (
            "get_changes"
            in change_feed.operations
        )

        assert (
            "get_latest_change_sequence"
            in change_feed.operations
        )


class TestCapabilityRegistryWithDisabledCapabilities:
    """Test registry behavior with disabled capabilities."""

    def test_get_capability_returns_disabled_descriptor(
        self,
    ):
        """Verify get_capability returns disabled cap."""
        registry = (
            ResearchWorkspaceCapabilities()
        )

        registry._capabilities[
            "experimental"
        ] = (
            ResearchWorkspaceCapabilityDescriptor(

                capability=(
                    ResearchWorkspaceCapability
                    .SUBSCRIPTIONS
                ),

                description="Experimental",

                operations=("test",),

                enabled=False,
            )
        )

        capability = (
            registry.get_capability(
                "experimental"
            )
        )

        assert capability is not None

        assert capability.enabled is False

    def test_supports_distinguishes_disabled_from_unknown(
        self,
    ):
        """Verify supports() distinguishes states."""
        registry = (
            ResearchWorkspaceCapabilities()
        )

        # Add disabled capability
        registry._capabilities[
            "disabled_cap"
        ] = (
            ResearchWorkspaceCapabilityDescriptor(

                capability=(
                    ResearchWorkspaceCapability
                    .ACTIVITY
                ),

                description="Disabled",

                operations=("op",),

                enabled=False,
            )
        )

        # get_capability returns both disabled
        # and unknown
        disabled = (
            registry.get_capability(
                "disabled_cap"
            )
        )

        unknown = (
            registry.get_capability(
                "unknown_cap"
            )
        )

        assert disabled is not None

        assert unknown is None

        # But supports() returns False for both
        assert (
            registry.supports(
                "disabled_cap"
            )
        ) is False

        assert (
            registry.supports(
                "unknown_cap"
            )
        ) is False
