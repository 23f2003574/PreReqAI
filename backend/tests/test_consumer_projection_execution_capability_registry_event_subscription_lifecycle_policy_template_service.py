import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicy,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyBuilder,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplate,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateError,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateService,
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


def _build_template(template_id, initial_state=None, policy=None):
    return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplate(
        template_id=template_id,

        template_name=template_id,

        description=f"Template {template_id}.",

        lifecycle_policy=(
            policy
            if policy is not None
            else _build_policy(
                initial_state
                or ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.REGISTERED,
            )
        ),
    )


class TestRegisterTemplate:
    """A single template can be registered and later found."""

    def test_register_template(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateService()
        template = _build_template("standard-registration")

        service.register(template)

        assert service.find("standard-registration") is template


class TestReplaceTemplate:
    """An already-registered template can be replaced in place."""

    def test_replace_template(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateService()
        service.register(_build_template("zeta"))
        service.register(_build_template("standard-registration"))
        service.register(_build_template("alpha"))

        replacement = _build_template(
            "standard-registration",
            initial_state=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.ACTIVE,
        )

        service.replace(replacement)

        assert service.find("standard-registration") is replacement
        assert [
            template.template_id
            for template in service.list()
        ] == ["zeta", "standard-registration", "alpha"]


class TestReplaceMissingTemplate:
    """Replacing a template that was never registered is rejected."""

    def test_replace_missing_template(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateError
        ):
            service.replace(_build_template("does-not-exist"))


class TestRemoveTemplate:
    """Removing an existing template removes it."""

    def test_remove_template(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateService()
        service.register(_build_template("standard-registration"))

        service.remove("standard-registration")

        assert service.find("standard-registration") is None
        assert service.contains("standard-registration") is False


class TestRemoveMissingTemplate:
    """Removing a template ID that was never registered is a no-op."""

    def test_remove_missing_template(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateService()
        template = _build_template("standard-registration")
        service.register(template)

        service.remove("does-not-exist")

        assert service.find("standard-registration") is template


class TestInstantiateTemplate:
    """Instantiating a template produces a new, equivalent lifecycle policy."""

    def test_instantiate_template(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateService()
        policy = _build_policy(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecycleState.REGISTERED,
        )
        service.register(
            _build_template(
                "standard-registration",
                policy=policy,
            )
        )

        instantiated = service.instantiate("standard-registration")

        assert isinstance(
            instantiated,
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicy,
        )
        assert instantiated == policy
        assert instantiated is not policy


class TestInstantiateMissingTemplate:
    """Instantiating a template ID that was never registered is rejected."""

    def test_instantiate_missing_template(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateError
        ):
            service.instantiate("does-not-exist")


class TestLookupExistingTemplate:
    """An existing template is found by contains() and find()."""

    def test_lookup_existing_template(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateService()
        template = _build_template("standard-registration")
        service.register(template)

        assert service.contains("standard-registration") is True
        assert service.find("standard-registration") is template


class TestLookupMissingTemplate:
    """A missing template is not found by contains() or find()."""

    def test_lookup_missing_template(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateService()

        assert service.contains("does-not-exist") is False
        assert service.find("does-not-exist") is None


class TestOrderingPreserved:
    """Templates are listed in registration order."""

    def test_ordering_preserved(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateService()
        service.register(_build_template("zeta"))
        service.register(_build_template("alpha"))
        service.register(_build_template("mid"))

        assert [
            template.template_id
            for template in service.list()
        ] == ["zeta", "alpha", "mid"]


class TestImmutableCollection:
    """A previously listed snapshot is unaffected by later registrations."""

    def test_immutable_collection(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateService()
        service.register(_build_template("standard-registration"))

        snapshot = service.list()

        service.register(_build_template("another-template"))

        assert len(snapshot) == 1
        assert len(service.list()) == 2


class TestRejectDuplicateTemplateId:
    """Registering a second template with the same ID is rejected."""

    def test_reject_duplicate_template_id(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateService()
        service.register(_build_template("standard-registration"))

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateError
        ):
            service.register(_build_template("standard-registration"))

        assert len(service.list()) == 1


class TestRejectNoneTemplate:
    """Registering a None template is rejected."""

    def test_reject_none_template(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateError
        ):
            service.register(None)


class TestRejectBlankTemplateId:
    """Registering a template with a blank template ID is rejected."""

    def test_reject_blank_template_id(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateError
        ):
            service.register(_build_template("   "))


class TestRejectMissingLifecyclePolicy:
    """Registering a template with a missing lifecycle policy is rejected."""

    def test_reject_missing_lifecycle_policy(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateService()
        template = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplate(
            template_id="standard-registration",

            template_name="Standard Registration",

            description="A standard registration lifecycle policy.",

            lifecycle_policy=None,
        )

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateError
        ):
            service.register(template)


class TestRejectWrongType:
    """Registering a non-template object is rejected."""

    def test_reject_wrong_type(self):
        service = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateService()

        with pytest.raises(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateError
        ):
            service.register("not-a-template")
