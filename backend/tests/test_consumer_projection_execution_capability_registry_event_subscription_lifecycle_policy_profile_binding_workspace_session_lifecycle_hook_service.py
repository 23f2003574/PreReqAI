import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionHookResult as HookResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLifecycleHook as Hook,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLifecycleHookError as Error,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionLifecycleHookService as HookService,
)


def _hook(hook_id, event="START", handler=None, enabled=True):
    return Hook(
        hook_id=hook_id,
        event=event,
        handler=handler if handler is not None else (lambda session_id: None),
        enabled=enabled,
    )


class TestWorkspaceSessionLifecycleHookService:
    def test_register_hook(self):
        service = HookService()

        registered = service.register(_hook("hook-1"))

        assert isinstance(registered, Hook)
        assert service.hooks("START") == (registered,)

    def test_enable_disable_hook(self):
        service = HookService()
        service.register(_hook("hook-1", enabled=True))

        service.disable("hook-1")
        assert service.hooks("START")[0].enabled is False

        service.enable("hook-1")
        assert service.hooks("START")[0].enabled is True

    def test_hook_execution(self):
        service = HookService()
        calls = []

        service.register(_hook("hook-1", handler=lambda session_id: calls.append(session_id)))

        results = service.execute("START", "session-1")

        assert calls == ["session-1"]
        assert len(results) == 1
        assert isinstance(results[0], HookResult)
        assert results[0].hook_id == "hook-1"
        assert results[0].executed is True
        assert results[0].duration_ms >= 0

    def test_execution_ordering(self):
        service = HookService()
        order = []

        service.register(_hook("hook-1", handler=lambda session_id: order.append("hook-1")))
        service.register(_hook("hook-2", handler=lambda session_id: order.append("hook-2")))
        service.register(_hook("hook-3", handler=lambda session_id: order.append("hook-3")))

        results = service.execute("START", "session-1")

        assert order == ["hook-1", "hook-2", "hook-3"]
        assert [result.hook_id for result in results] == ["hook-1", "hook-2", "hook-3"]

    def test_disabled_hook_skipped(self):
        service = HookService()
        calls = []

        service.register(_hook("hook-1", handler=lambda session_id: calls.append("hook-1"), enabled=False))
        service.register(_hook("hook-2", handler=lambda session_id: calls.append("hook-2")))

        results = service.execute("START", "session-1")

        assert calls == ["hook-2"]
        assert [result.hook_id for result in results] == ["hook-2"]

    def test_hook_failure_isolation(self):
        service = HookService()
        calls = []

        def _failing(session_id):
            raise RuntimeError("boom")

        service.register(_hook("hook-1", handler=_failing))
        service.register(_hook("hook-2", handler=lambda session_id: calls.append("hook-2")))

        results = service.execute("START", "session-1")

        assert calls == ["hook-2"]  # hook-2 still ran despite hook-1 failing
        assert results[0].hook_id == "hook-1"
        assert results[0].executed is False
        assert results[1].hook_id == "hook-2"
        assert results[1].executed is True

    def test_duplicate_registration_rejection(self):
        service = HookService()
        service.register(_hook("hook-1"))

        with pytest.raises(Error):
            service.register(_hook("hook-1"))

    def test_invalid_event_rejection(self):
        with pytest.raises(Error):
            _hook("hook-1", event="UNKNOWN_EVENT")

        service = HookService()

        with pytest.raises(Error):
            service.execute("UNKNOWN_EVENT", "session-1")

        with pytest.raises(Error):
            service.hooks("UNKNOWN_EVENT")

    def test_blank_and_unknown_id_rejection(self):
        service = HookService()

        with pytest.raises(Error):
            service.enable("   ")

        with pytest.raises(Error):
            service.enable("unknown-hook")

        with pytest.raises(Error):
            service.disable("   ")

        with pytest.raises(Error):
            service.disable("unknown-hook")

        with pytest.raises(Error):
            service.execute("START", "   ")

        with pytest.raises(Error):
            service.register("not-a-hook")
