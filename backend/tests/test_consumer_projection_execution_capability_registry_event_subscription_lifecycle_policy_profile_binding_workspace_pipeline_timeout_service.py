from dataclasses import (
    dataclass,
)

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.session import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipeline as Pipeline,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineService as PipelineService,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionPipelineStatus as PipelineStatus,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineCancellationResult as CancellationResult,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineStage as Stage,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineTimeoutError as Error,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineTimeoutPolicy as TimeoutPolicy,
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineTimeoutService as TimeoutService,
)


@dataclass(frozen=True)
class _RunningStage:
    """Minimal stand-in for the (stage_id, started_at, timeout_policy) protocol expected by TimeoutService."""

    stage_id: str
    started_at: datetime
    timeout_policy: TimeoutPolicy


def _policy(timeout_seconds=30, cancel_on_timeout=True, notify_on_timeout=False):
    return TimeoutPolicy(
        timeout_seconds=timeout_seconds,
        cancel_on_timeout=cancel_on_timeout,
        notify_on_timeout=notify_on_timeout,
    )


def _running(stage_id, started_seconds_ago, policy=None):
    return _RunningStage(
        stage_id=stage_id,
        started_at=datetime.now(timezone.utc) - timedelta(seconds=started_seconds_ago),
        timeout_policy=policy if policy is not None else _policy(),
    )


class TestWorkspacePipelineTimeoutService:
    def test_timeout_detection(self):
        service = TimeoutService()

        fresh = _running("stage-1", started_seconds_ago=5, policy=_policy(timeout_seconds=30))
        expired = _running("stage-2", started_seconds_ago=45, policy=_policy(timeout_seconds=30))

        assert service.is_expired(fresh) is False
        assert service.is_expired(expired) is True

        assert service.check_timeout(fresh) is False
        assert service.check_timeout(expired) is True

    def test_successful_cancellation(self):
        service = TimeoutService()

        result = service.cancel("stage-1", reason="Manually cancelled.")

        assert isinstance(result, CancellationResult)
        assert result.stage_id == "stage-1"
        assert result.cancelled is True
        assert result.reason == "Manually cancelled."
        assert service.cancellation("stage-1") == result

    def test_remaining_time_calculation(self):
        service = TimeoutService()

        stage = _running("stage-1", started_seconds_ago=10, policy=_policy(timeout_seconds=30))
        remaining = service.remaining_time(stage)

        assert 19 <= remaining <= 20

        expired = _running("stage-2", started_seconds_ago=100, policy=_policy(timeout_seconds=30))
        assert service.remaining_time(expired) == 0.0

    def test_completed_stage_rejection(self):
        service = TimeoutService()

        service.complete("stage-1")

        with pytest.raises(Error):
            service.cancel("stage-1")

        # complete() is idempotent for a stage that has not been cancelled.
        service.complete("stage-1")

    def test_completed_stage_rejection_after_cancel(self):
        service = TimeoutService()

        service.cancel("stage-1")

        with pytest.raises(Error):
            service.complete("stage-1")

    def test_duplicate_cancellation_rejection(self):
        service = TimeoutService()

        service.cancel("stage-1", reason="First cancellation.")

        with pytest.raises(Error):
            service.cancel("stage-1", reason="Second cancellation.")

    def test_auto_cancel_on_timeout_records_reason(self):
        service = TimeoutService()

        expired = _running(
            "stage-1",
            started_seconds_ago=60,
            policy=_policy(timeout_seconds=1, cancel_on_timeout=True),
        )

        assert service.check_timeout(expired) is True

        recorded = service.cancellation("stage-1")
        assert recorded is not None
        assert recorded.cancelled is True
        assert "timeout" in recorded.reason.lower()

        # A second check_timeout() call must not attempt to re-cancel.
        assert service.check_timeout(expired) is True

    def test_no_auto_cancel_when_policy_disables_it(self):
        service = TimeoutService()

        expired = _running(
            "stage-1",
            started_seconds_ago=60,
            policy=_policy(timeout_seconds=1, cancel_on_timeout=False),
        )

        assert service.check_timeout(expired) is True
        assert service.cancellation("stage-1") is None

    def test_validation_rejections(self):
        with pytest.raises(Error):
            TimeoutPolicy(timeout_seconds=0, cancel_on_timeout=True, notify_on_timeout=False)

        with pytest.raises(Error):
            TimeoutPolicy(timeout_seconds=-5, cancel_on_timeout=True, notify_on_timeout=False)

        with pytest.raises(Error):
            CancellationResult(stage_id="   ", cancelled=True, reason="x")

        with pytest.raises(Error):
            CancellationResult(stage_id="stage-1", cancelled=True, reason="   ")

        service = TimeoutService()

        with pytest.raises(Error):
            service.cancel("   ")

        with pytest.raises(Error):
            service.is_expired(None)

        with pytest.raises(Error):
            service.remaining_time(_RunningStage(stage_id="   ", started_at=datetime.now(timezone.utc), timeout_policy=_policy()))

    def test_pipeline_transitions_to_cancelled_on_stage_timeout(self):
        timeout_service = TimeoutService()
        pipeline_service = None

        def _validation(workspace_id, configuration):
            pass

        def _slow_review(workspace_id, configuration):
            stage = _running("stage-2", started_seconds_ago=120, policy=_policy(timeout_seconds=5))

            if timeout_service.check_timeout(stage):
                pipeline_service.cancel("pipeline-1")

        pipeline_service = PipelineService(
            stage_executors={
                "validation": _validation,
                "review": _slow_review,
            }
        )

        stages = (
            Stage(stage_id="stage-1", type="validation", order=0),
            Stage(stage_id="stage-2", type="review", order=1),
        )

        pipeline_service.create(
            Pipeline(pipeline_id="pipeline-1", workspace_id="workspace-1", name="release", stages=stages)
        )

        result = pipeline_service.execute("pipeline-1")

        assert result.status == PipelineStatus.CANCELLED
        assert timeout_service.cancellation("stage-2").cancelled is True
