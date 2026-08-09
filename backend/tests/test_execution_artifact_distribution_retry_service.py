import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipeline as Pipeline,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineService as PipelineService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineStage as Stage,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionService as SessionService,
    DistributionRetryPolicy,
    ExecutionArtifact,
    ExecutionArtifactDistributionChannel,
    ExecutionArtifactDistributionDeliveryService,
    ExecutionArtifactDistributionRetryError as Error,
    ExecutionArtifactDistributionRetryService,
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
    retry_service = ExecutionArtifactDistributionRetryService(delivery_service)

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
        "retry_service": retry_service,
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


def _policy(policy_id="policy-1", max_attempts=3, backoff_seconds=10, enabled=True):
    return DistributionRetryPolicy(
        policy_id=policy_id,
        max_attempts=max_attempts,
        backoff_seconds=backoff_seconds,
        enabled=enabled,
    )


def _failed_delivery(env):
    """
    Build a delivery that fails on its first attempt because its
    artifact is not yet registered with the artifact registry, and
    that can be made to succeed on a later attempt simply by
    registering it (see test_successful_retry).
    """

    env["distribution_service"].register(_channel("channel-1"))
    env["batch_registry"].track("batch-1", "channel-1")
    delivery = env["delivery_service"].create("batch-1", "artifact-1")
    return env["delivery_service"].deliver(delivery.delivery_id)


class TestExecutionArtifactDistributionRetryService:
    def test_configure_policy(self):
        env = _build()

        configured = env["retry_service"].configure(_policy())

        assert isinstance(configured, DistributionRetryPolicy)
        assert configured.policy_id == "policy-1"

    def test_retry_delivery(self):
        env = _build()
        failed = _failed_delivery(env)
        env["retry_service"].configure(_policy())

        retried = env["retry_service"].retry(failed.delivery_id)

        assert retried.attempts == 2

    def test_max_attempt_rejection(self):
        env = _build()
        failed = _failed_delivery(env)
        env["retry_service"].configure(_policy(max_attempts=1))

        assert env["retry_service"].can_retry(failed.delivery_id) is False

        with pytest.raises(Error):
            env["retry_service"].retry(failed.delivery_id)

    def test_backoff_calculation(self):
        env = _build()
        failed = _failed_delivery(env)
        env["retry_service"].configure(_policy(backoff_seconds=10))

        assert env["retry_service"].next_attempt(failed.delivery_id) == 10

        retried = env["retry_service"].retry(failed.delivery_id)

        assert env["retry_service"].next_attempt(retried.delivery_id) == 20

    def test_disabled_policy(self):
        env = _build()
        failed = _failed_delivery(env)
        env["retry_service"].configure(_policy(enabled=False))

        assert env["retry_service"].can_retry(failed.delivery_id) is False

        with pytest.raises(Error):
            env["retry_service"].retry(failed.delivery_id)

    def test_successful_retry(self):
        env = _build()
        failed = _failed_delivery(env)
        assert failed.status == "FAILED"

        env["retry_service"].configure(_policy())
        _register_artifact(env, "artifact-1")

        assert env["retry_service"].can_retry(failed.delivery_id) is True

        retried = env["retry_service"].retry(failed.delivery_id)

        assert retried.status == "DELIVERED"
        assert retried.attempts == 2
