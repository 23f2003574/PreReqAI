import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipeline as Pipeline,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineService as PipelineService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineStatus as PipelineStatus,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelinePlugin as Plugin,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelinePluginError as Error,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelinePluginResult as PluginResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelinePluginService as PluginService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineStage as Stage,
)


def _plugin(plugin_id, stage_type="validation", enabled=True, name=None):
    return Plugin(
        plugin_id=plugin_id,
        name=name if name is not None else plugin_id,
        stage_type=stage_type,
        enabled=enabled,
    )


class TestWorkspacePipelinePluginService:
    def test_register_plugin(self):
        service = PluginService()

        plugin = service.register(_plugin("plugin-1"), lambda stage_id: None)

        assert isinstance(plugin, Plugin)
        assert plugin.enabled is True
        assert service.plugins("validation") == (plugin,)

        with pytest.raises(Error):
            service.register(None, lambda stage_id: None)

        with pytest.raises(Error):
            service.register(_plugin("plugin-2"), "not_callable")

    def test_enable_disable_plugin(self):
        service = PluginService()
        service.register(_plugin("plugin-1", enabled=True), lambda stage_id: None)

        disabled = service.disable("plugin-1")
        assert disabled.enabled is False

        enabled = service.enable("plugin-1")
        assert enabled.enabled is True

        with pytest.raises(Error):
            service.enable("unknown-plugin")

        with pytest.raises(Error):
            service.disable("unknown-plugin")

    def test_execution_order(self):
        service = PluginService()
        calls = []

        service.register(_plugin("plugin-c"), lambda stage_id: calls.append("plugin-c"))
        service.register(_plugin("plugin-a"), lambda stage_id: calls.append("plugin-a"))
        service.register(_plugin("plugin-b"), lambda stage_id: calls.append("plugin-b"))

        results = service.execute("stage-1", "validation")

        assert calls == ["plugin-c", "plugin-a", "plugin-b"]
        assert [result.plugin_id for result in results] == ["plugin-c", "plugin-a", "plugin-b"]
        assert all(result.executed for result in results)
        assert all(result.error is None for result in results)

    def test_plugin_failure_isolation(self):
        service = PluginService()
        calls = []

        def _failing(stage_id):
            raise RuntimeError("plugin exploded")

        service.register(_plugin("plugin-1"), lambda stage_id: calls.append("plugin-1"))
        service.register(_plugin("plugin-2"), _failing)
        service.register(_plugin("plugin-3"), lambda stage_id: calls.append("plugin-3"))

        results = service.execute("stage-1", "validation")

        assert calls == ["plugin-1", "plugin-3"]

        by_id = {result.plugin_id: result for result in results}
        assert by_id["plugin-1"].executed is True
        assert by_id["plugin-1"].error is None
        assert by_id["plugin-2"].executed is True
        assert "plugin exploded" in by_id["plugin-2"].error
        assert by_id["plugin-3"].executed is True
        assert by_id["plugin-3"].error is None

    def test_duplicate_registration_rejection(self):
        service = PluginService()
        service.register(_plugin("plugin-1"), lambda stage_id: None)

        with pytest.raises(Error):
            service.register(_plugin("plugin-1"), lambda stage_id: None)

        with pytest.raises(Error):
            _plugin("   ")

        with pytest.raises(Error):
            _plugin("plugin-x", stage_type="not_a_real_type")

    def test_stage_plugin_lookup(self):
        service = PluginService()

        service.register(_plugin("plugin-1", stage_type="validation"), lambda stage_id: None)
        service.register(_plugin("plugin-2", stage_type="review"), lambda stage_id: None)
        service.register(_plugin("plugin-3", stage_type="validation"), lambda stage_id: None)

        validation_plugins = service.plugins("validation")
        assert [plugin.plugin_id for plugin in validation_plugins] == ["plugin-1", "plugin-3"]

        review_plugins = service.plugins("review")
        assert [plugin.plugin_id for plugin in review_plugins] == ["plugin-2"]

        assert service.plugins("deployment") == ()

        with pytest.raises(Error):
            service.plugins("not_a_real_type")

    def test_skip_disabled_plugins(self):
        service = PluginService()
        calls = []

        service.register(_plugin("plugin-1"), lambda stage_id: calls.append("plugin-1"))
        service.register(_plugin("plugin-2"), lambda stage_id: calls.append("plugin-2"))
        service.disable("plugin-2")

        results = service.execute("stage-1", "validation")

        assert calls == ["plugin-1"]

        by_id = {result.plugin_id: result for result in results}
        assert by_id["plugin-1"].executed is True
        assert by_id["plugin-2"].executed is False
        assert by_id["plugin-2"].duration_ms == 0.0

    def test_pipeline_stage_invokes_plugins(self):
        plugin_service = PluginService()
        calls = []

        plugin_service.register(_plugin("plugin-1"), lambda stage_id: calls.append((stage_id, "plugin-1")))

        def _validation(workspace_id, configuration):
            plugin_service.execute("stage-1", "validation")

        pipeline_service = PipelineService(stage_executors={"validation": _validation})
        pipeline_service.create(
            Pipeline(
                pipeline_id="pipeline-1",
                workspace_id="workspace-1",
                name="release",
                stages=(Stage(stage_id="stage-1", type="validation", order=0),),
            )
        )

        result = pipeline_service.execute("pipeline-1")

        assert result.status == PipelineStatus.COMPLETED
        assert calls == [("stage-1", "plugin-1")]
