import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipeline as Pipeline,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineService as PipelineService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineStage as Stage,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionService as SessionService,
    ArtifactDistributionDelivery,
    ExecutionArtifact,
    ExecutionArtifactDistributionChannel,
    ExecutionArtifactDistributionDeliveryError as Error,
    ExecutionArtifactDistributionDeliveryService,
    ExecutionArtifactDistributionService,
    ExecutionArtifactService,
)


class _Batch:
    def __init__(self, batch_id, channel_id):
        self.batch_id = batch_id
        self.channel_id = channel_id


class _BatchRegistry:
    """Stand-in for the distribution batch service assumed by this commit."""

    def __init__(self):
        self._batches_by_id = {}

    def track(self, batch_id, channel_id):
        batch = _Batch(batch_id, channel_id)
        self._batches_by_id[batch_id] = batch
        return batch

    def get(self, batch_id):
        batch = self._batches_by_id.get(batch_id)

        if batch is None:
            raise KeyError(batch_id)

        return batch


def _build():
    pipeline_service = PipelineService(stage_executors={"validation": lambda w, c: None})
    session_service = SessionService(pipeline_service)
    artifact_service = ExecutionArtifactService(session_service)
    distribution_service = ExecutionArtifactDistributionService(artifact_service)
    batch_registry = _BatchRegistry()
    delivery_service = ExecutionArtifactDistributionDeliveryService(batch_registry, distribution_service)

    pipeline_service.create(
        Pipeline(
            pipeline_id="pipeline-1",
            workspace_id="workspace-1",
            name="release",
            stages=(Stage(stage_id="stage-1", type="validation", order=0),),
        )
    )
    session = session_service.start("pipeline-1", owner="user-1")

    return {
        "artifact_service": artifact_service,
        "distribution_service": distribution_service,
        "batch_registry": batch_registry,
        "delivery_service": delivery_service,
        "session": session,
    }


def _register_artifact(env, artifact_id):
    return env["artifact_service"].register(
        env["session"].session_id,
        ExecutionArtifact(
            artifact_id=artifact_id,
            session_id=env["session"].session_id,
            name=f"{artifact_id}.log",
            type="log",
            location=f"/tmp/{artifact_id}.log",
        ),
    )


def _channel(channel_id, enabled=True):
    return ExecutionArtifactDistributionChannel(
        channel_id=channel_id,
        name=f"Channel {channel_id}",
        type="webhook",
        endpoint=f"https://example.test/hooks/{channel_id}",
        enabled=enabled,
    )


class TestExecutionArtifactDistributionDeliveryService:
    def test_create_delivery(self):
        env = _build()
        env["distribution_service"].register(_channel("channel-1"))
        env["batch_registry"].track("batch-1", "channel-1")
        _register_artifact(env, "artifact-1")

        delivery = env["delivery_service"].create("batch-1", "artifact-1")

        assert isinstance(delivery, ArtifactDistributionDelivery)
        assert delivery.status == "PENDING"
        assert delivery.attempts == 0
        assert delivery.channel_id == "channel-1"

    def test_successful_delivery(self):
        env = _build()
        env["distribution_service"].register(_channel("channel-1"))
        env["batch_registry"].track("batch-1", "channel-1")
        _register_artifact(env, "artifact-1")
        delivery = env["delivery_service"].create("batch-1", "artifact-1")

        delivered = env["delivery_service"].deliver(delivery.delivery_id)

        assert delivered.status == "DELIVERED"
        assert delivered.attempts == 1
        assert delivered.delivered_at is not None

    def test_retry_failure(self):
        env = _build()
        env["distribution_service"].register(_channel("channel-1", enabled=False))
        env["batch_registry"].track("batch-1", "channel-1")
        _register_artifact(env, "artifact-1")
        delivery = env["delivery_service"].create("batch-1", "artifact-1")

        failed = env["delivery_service"].deliver(delivery.delivery_id)
        assert failed.status == "FAILED"
        assert failed.attempts == 1

        retried = env["delivery_service"].retry(delivery.delivery_id)
        assert retried.status == "FAILED"
        assert retried.attempts == 2

    def test_completed_retry_rejection(self):
        env = _build()
        env["distribution_service"].register(_channel("channel-1"))
        env["batch_registry"].track("batch-1", "channel-1")
        _register_artifact(env, "artifact-1")
        delivery = env["delivery_service"].create("batch-1", "artifact-1")
        env["delivery_service"].deliver(delivery.delivery_id)

        with pytest.raises(Error):
            env["delivery_service"].retry(delivery.delivery_id)

    def test_pending_lookup(self):
        env = _build()
        env["distribution_service"].register(_channel("channel-1"))
        env["batch_registry"].track("batch-1", "channel-1")
        _register_artifact(env, "artifact-1")
        _register_artifact(env, "artifact-2")
        delivery_a = env["delivery_service"].create("batch-1", "artifact-1")
        delivery_b = env["delivery_service"].create("batch-1", "artifact-2")

        env["delivery_service"].deliver(delivery_a.delivery_id)

        pending = env["delivery_service"].pending("batch-1")

        assert [entry.delivery_id for entry in pending] == [delivery_b.delivery_id]

    def test_attempt_tracking(self):
        env = _build()
        env["distribution_service"].register(_channel("channel-1", enabled=False))
        env["batch_registry"].track("batch-1", "channel-1")
        _register_artifact(env, "artifact-1")
        delivery = env["delivery_service"].create("batch-1", "artifact-1")

        env["delivery_service"].deliver(delivery.delivery_id)
        env["delivery_service"].retry(delivery.delivery_id)
        env["delivery_service"].retry(delivery.delivery_id)

        status = env["delivery_service"].status(delivery.delivery_id)

        assert status.attempts == 3
