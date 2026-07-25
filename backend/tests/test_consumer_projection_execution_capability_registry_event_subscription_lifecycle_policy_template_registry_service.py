import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplate,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRegistryError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRegistryService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRegistrySnapshot,
)


def _build_policy(initial_state):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyBuilder().build(
        (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.REGISTERED,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.ACTIVE,
        ),
        initial_state,
    )


def _build_template(template_id, policy=None):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplate(
        template_id=template_id,

        template_name=template_id,

        description=f"Template {template_id}.",

        lifecycle_policy=(
            policy
            if policy is not None
            else _build_policy(
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.REGISTERED,
            )
        ),
    )


class TestRegisterTemplate:
    """A single template can be registered and later found."""

    def test_register_template(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRegistryService()
        template = _build_template("standard-registration")

        service.register(template)

        assert service.find("standard-registration") is template


class TestReplaceTemplate:
    """An already-registered template can be replaced in place."""

    def test_replace_template(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRegistryService()
        service.register(_build_template("zeta"))
        service.register(_build_template("standard-registration"))
        service.register(_build_template("alpha"))

        replacement = _build_template("standard-registration")

        service.replace(replacement)

        assert service.find("standard-registration") is replacement
        assert [
            template.template_id
            for template in service.list()
        ] == ["zeta", "standard-registration", "alpha"]


class TestReplaceMissingTemplate:
    """Replacing a template that was never registered is rejected."""

    def test_replace_missing_template(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRegistryService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRegistryError
        ):
            service.replace(_build_template("does-not-exist"))


class TestUnregisterTemplate:
    """Unregistering an existing template removes it."""

    def test_unregister_template(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRegistryService()
        service.register(_build_template("standard-registration"))

        service.unregister("standard-registration")

        assert service.find("standard-registration") is None
        assert service.contains("standard-registration") is False


class TestUnregisterMissingTemplate:
    """Unregistering a template ID that was never registered is rejected."""

    def test_unregister_missing_template(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRegistryService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRegistryError
        ):
            service.unregister("does-not-exist")


class TestLookupExistingTemplate:
    """An existing template is found by find()."""

    def test_lookup_existing_template(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRegistryService()
        template = _build_template("standard-registration")
        service.register(template)

        assert service.find("standard-registration") is template


class TestLookupMissingTemplate:
    """A missing template is not found by find()."""

    def test_lookup_missing_template(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRegistryService()

        assert service.find("does-not-exist") is None


class TestContains:
    """contains() reports registration state accurately."""

    def test_contains(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRegistryService()
        service.register(_build_template("standard-registration"))

        assert service.contains("standard-registration") is True
        assert service.contains("does-not-exist") is False


class TestListOrdering:
    """Templates are listed in registration order."""

    def test_list_ordering(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRegistryService()
        service.register(_build_template("zeta"))
        service.register(_build_template("alpha"))
        service.register(_build_template("mid"))

        assert [
            template.template_id
            for template in service.list()
        ] == ["zeta", "alpha", "mid"]


class TestSnapshotGeneration:
    """snapshot() reflects the registry's current state."""

    def test_snapshot_generation(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRegistryService()
        service.register(_build_template("zeta"))
        service.register(_build_template("alpha"))

        snapshot = service.snapshot()

        assert isinstance(
            snapshot,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRegistrySnapshot,
        )
        assert snapshot.template_count == 2
        assert snapshot.template_identifiers == ("zeta", "alpha")

        service.register(_build_template("mid"))

        assert snapshot.template_count == 2
        assert service.snapshot().template_count == 3


class TestImmutableRegistry:
    """A previously listed snapshot is unaffected by later registrations."""

    def test_immutable_registry(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRegistryService()
        service.register(_build_template("standard-registration"))

        listed = service.list()

        service.register(_build_template("another-template"))

        assert len(listed) == 1
        assert len(service.list()) == 2


class TestRejectNoneTemplate:
    """Registering a None template is rejected."""

    def test_reject_none_template(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRegistryService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRegistryError
        ):
            service.register(None)


class TestRejectDuplicateTemplateId:
    """Registering a second template with the same ID is rejected."""

    def test_reject_duplicate_template_id(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRegistryService()
        service.register(_build_template("standard-registration"))

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRegistryError
        ):
            service.register(_build_template("standard-registration"))

        assert len(service.list()) == 1


class TestRejectBlankIdentifier:
    """Registering a template with a blank template ID is rejected."""

    def test_reject_blank_identifier(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRegistryService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRegistryError
        ):
            service.register(_build_template("   "))


class TestRejectWrongType:
    """Registering a non-template object is rejected."""

    def test_reject_wrong_type(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRegistryService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRegistryError
        ):
            service.register("not-a-template")
