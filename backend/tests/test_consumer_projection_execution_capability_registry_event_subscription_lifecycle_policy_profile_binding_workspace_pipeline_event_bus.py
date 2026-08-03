from datetime import (
    datetime,
    timezone,
)

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipeline as Pipeline,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineService as PipelineService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineStatus as PipelineStatus,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineEvent as Event,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineEventBus as EventBus,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineEventError as Error,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineEventResult as EventResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineStage as Stage,
)


def _event(event_id, event_type="stage_completed", pipeline_id="pipeline-1", stage_id="stage-1", payload=None):
    return Event(
        event_id=event_id,
        pipeline_id=pipeline_id,
        stage_id=stage_id,
        event_type=event_type,
        timestamp=datetime.now(timezone.utc),
        payload=payload if payload is not None else {},
    )


class TestWorkspacePipelineEventBus:
    def test_publish_event(self):
        bus = EventBus()

        result = bus.publish(_event("event-1"))

        assert isinstance(result, EventResult)
        assert result.published is True
        assert result.subscribers_notified == 0

        pending = bus.pending_events()
        assert len(pending) == 1
        assert pending[0].event_id == "event-1"

        duplicate_result = bus.publish(_event("event-1"))
        assert duplicate_result.published is False
        assert len(bus.pending_events()) == 1

    def test_subscribe_and_unsubscribe(self):
        bus = EventBus()
        received = []

        def _handler(event):
            received.append(event)

        bus.subscribe("stage_completed", _handler)
        bus.publish(_event("event-1"))
        bus.dispatch_pending()

        assert len(received) == 1

        bus.unsubscribe("stage_completed", _handler)
        bus.publish(_event("event-2"))
        bus.dispatch_pending()

        assert len(received) == 1

        with pytest.raises(Error):
            bus.unsubscribe("stage_completed", _handler)

    def test_fifo_dispatch(self):
        bus = EventBus()
        order = []

        bus.subscribe("stage_started", lambda event: order.append(event.event_id))

        bus.publish(_event("event-1", event_type="stage_started"))
        bus.publish(_event("event-2", event_type="stage_started"))
        bus.publish(_event("event-3", event_type="stage_started"))

        assert [event.event_id for event in bus.pending_events()] == ["event-1", "event-2", "event-3"]

        results = bus.dispatch_pending()

        assert order == ["event-1", "event-2", "event-3"]
        assert len(results) == 3
        assert all(result.subscribers_notified == 1 for result in results)
        assert bus.pending_events() == ()

    def test_duplicate_subscription_rejection(self):
        bus = EventBus()

        def _handler(event):
            pass

        bus.subscribe("stage_failed", _handler)

        with pytest.raises(Error):
            bus.subscribe("stage_failed", _handler)

        with pytest.raises(Error):
            bus.subscribe("not_a_real_type", _handler)

        with pytest.raises(Error):
            bus.subscribe("stage_failed", "not_callable")

    def test_subscriber_failure_isolation(self):
        bus = EventBus()
        received = []

        def _failing_handler(event):
            raise RuntimeError("boom")

        def _working_handler(event):
            received.append(event.event_id)

        bus.subscribe("stage_completed", _failing_handler)
        bus.subscribe("stage_completed", _working_handler)

        bus.publish(_event("event-1"))
        bus.publish(_event("event-2"))

        results = bus.dispatch_pending()

        assert received == ["event-1", "event-2"]
        assert [result.subscribers_notified for result in results] == [1, 1]

    def test_pending_event_retrieval(self):
        bus = EventBus()

        assert bus.pending_events() == ()

        bus.publish(_event("event-1"))
        bus.publish(_event("event-2"))

        pending = bus.pending_events()
        assert [event.event_id for event in pending] == ["event-1", "event-2"]

        bus.dispatch_pending()

        assert bus.pending_events() == ()

    def test_validation_rejections(self):
        with pytest.raises(Error):
            Event(
                event_id="   ",
                pipeline_id="pipeline-1",
                stage_id="stage-1",
                event_type="stage_completed",
                timestamp=datetime.now(timezone.utc),
                payload={},
            )

        with pytest.raises(Error):
            Event(
                event_id="event-1",
                pipeline_id="pipeline-1",
                stage_id="stage-1",
                event_type="not_a_real_type",
                timestamp=datetime.now(timezone.utc),
                payload={},
            )

        bus = EventBus()

        with pytest.raises(Error):
            bus.publish(None)

        with pytest.raises(Error):
            bus.publish("not_an_event")

        with pytest.raises(Error):
            bus.subscribe("   ", lambda event: None)

        with pytest.raises(Error):
            bus.unsubscribe("stage_completed", lambda event: None)

    def test_pipeline_publishes_stage_completed_events(self):
        bus = EventBus()
        received = []

        bus.subscribe("stage_completed", lambda event: received.append(event.stage_id))

        pipeline_service = PipelineService(
            stage_executors={
                "validation": lambda workspace_id, configuration: None,
                "review": lambda workspace_id, configuration: None,
            },
            event_bus=bus,
        )

        stages = (
            Stage(stage_id="stage-1", type="validation", order=0),
            Stage(stage_id="stage-2", type="review", order=1),
        )

        pipeline_service.create(
            Pipeline(pipeline_id="pipeline-1", workspace_id="workspace-1", name="release", stages=stages)
        )

        result = pipeline_service.execute("pipeline-1")

        assert result.status == PipelineStatus.COMPLETED
        assert len(bus.pending_events()) == 2

        bus.dispatch_pending()

        assert received == ["stage-1", "stage-2"]
