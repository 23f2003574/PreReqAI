import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionPolicy as Policy,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionEffectivePolicy as EffectivePolicy,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyInheritance as Inheritance,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyInheritanceError as Error,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyInheritanceService as InheritanceService,
)


def _policy(policy_id, max_runtime=3600, max_idle=300, allow_restore=True, enabled=True, name="standard"):
    return Policy(
        policy_id=policy_id,
        name=name,
        max_runtime=max_runtime,
        max_idle=max_idle,
        allow_restore=allow_restore,
        enabled=enabled,
    )


class TestWorkspaceSessionPolicyInheritanceService:
    def test_resolve_inherited_policy(self):
        service = InheritanceService()
        parent = _policy("parent", max_runtime=3600, max_idle=300)
        child = _policy("child", max_runtime=3600, max_idle=300)

        service.link(child, parent)
        effective = service.resolve("child")

        assert isinstance(effective, EffectivePolicy)
        assert effective.policy_id == "child"
        assert effective.resolved_configuration["max_runtime"] == 3600
        assert effective.resolved_configuration["max_idle"] == 300

    def test_override_fields(self):
        service = InheritanceService()
        parent = _policy("parent", max_runtime=3600, max_idle=300, allow_restore=True)
        child = _policy("child", max_runtime=1800, max_idle=300, allow_restore=True)

        inheritance = service.link(child, parent)

        assert isinstance(inheritance, Inheritance)
        assert inheritance.overridden_fields == ("max_runtime",)

        effective = service.resolve("child")
        assert effective.resolved_configuration["max_runtime"] == 1800
        assert effective.resolved_configuration["max_idle"] == 300

        # linking a second time without unlinking first is rejected: single parent inheritance
        with pytest.raises(Error):
            service.link(child, parent)

    def test_unlink_parent(self):
        service = InheritanceService()
        parent = _policy("parent", max_runtime=3600)
        child = _policy("child", max_runtime=1800)
        service.link(child, parent)

        service.unlink("child")

        effective = service.resolve("child")
        assert effective.resolved_configuration["max_runtime"] == 1800

        with pytest.raises(Error):
            service.unlink("child")

    def test_lineage_lookup(self):
        service = InheritanceService()
        grandparent = _policy("grandparent")
        parent = _policy("parent")
        child = _policy("child")

        service.link(parent, grandparent)
        service.link(child, parent)

        assert service.lineage("child") == ("child", "parent", "grandparent")
        assert service.lineage("parent") == ("parent", "grandparent")
        assert service.lineage("grandparent") == ("grandparent",)

        with pytest.raises(Error):
            service.lineage("unknown")

    def test_cycle_detection(self):
        service = InheritanceService()
        first = _policy("first")
        second = _policy("second")
        third = _policy("third")

        service.link(second, first)
        service.link(third, second)

        # first -> ... -> third already, so linking first under third would cycle
        with pytest.raises(Error):
            service.link(first, third)

        assert service.validate("third") is True

    def test_cache_invalidation(self):
        service = InheritanceService()
        parent = _policy("parent", max_runtime=3600)
        child = _policy("child", max_runtime=1800)
        service.link(child, parent)

        first_resolution = service.resolve("child")
        second_resolution = service.resolve("child")

        # unchanged structure: the cached result is returned as-is
        assert first_resolution is second_resolution
        assert first_resolution.resolved_configuration["max_idle"] == parent.max_idle

        service.unlink("child")
        third_resolution = service.resolve("child")

        # unlinking invalidates the cache: a fresh result reflects the new structure
        assert third_resolution is not first_resolution
        assert third_resolution.resolved_configuration["max_runtime"] == 1800
