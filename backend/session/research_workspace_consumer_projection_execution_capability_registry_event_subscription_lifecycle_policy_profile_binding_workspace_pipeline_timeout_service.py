from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_pipeline_timeout_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineTimeoutError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_pipeline_timeout_policy import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineTimeoutPolicy,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_pipeline_cancellation_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineCancellationResult,
)

_DEFAULT_CANCELLATION_REASON = "Stage cancelled."


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineTimeoutService:
    """
    Detects and acts on timeouts for consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding workspace pipeline stages, and tracks their cancellation.

    The service's responsibility is timing and cancellation
    bookkeeping, not running a stage or a pipeline itself. It does
    NOT execute stages or pipelines; whoever runs the pipeline (for
    example, a consumer projection execution capability registry
    event subscription lifecycle policy profile binding workspace
    execution pipeline service) is expected to call check_timeout()
    while a stage runs, and to transition its pipeline to CANCELLED
    once a stage this service reports as cancelled belongs to it.

    A "stage" argument accepted by check_timeout(), is_expired(), and
    remaining_time() is any object exposing:
    - `stage_id` (str): the stage's identifier
    - `started_at` (datetime): when the stage began running
    - `timeout_policy` (ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineTimeoutPolicy): the stage's timeout configuration

    Behavior:
    - is_expired() and remaining_time() are pure computations based
      entirely on the given stage's own started_at and timeout_policy
    - check_timeout() detects expiry and, if the stage's policy
      requests it, cancels the stage and records the cancellation
      reason
    - A stage must be marked complete() before it stops being
      eligible for cancellation; cancelling a completed or already
      cancelled stage is rejected

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self):
        self._cancellations = {}
        self._completed = set()
        self._lock = RLock()

    def check_timeout(self, stage) -> bool:
        """
        Check whether a running stage has exceeded its timeout, and
        cancel it if its policy requests automatic cancellation.

        Returns:
            True if the stage has timed out, False otherwise

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineTimeoutError:
                If stage is None or malformed
        """

        expired = self.is_expired(stage)

        if expired and stage.timeout_policy.cancel_on_timeout:
            with self._lock:
                already_settled = stage.stage_id in self._cancellations or stage.stage_id in self._completed

                if not already_settled:
                    self.cancel(
                        stage.stage_id,
                        reason=(
                            f"Stage exceeded its configured timeout of "
                            f"{stage.timeout_policy.timeout_seconds!r} seconds."
                        ),
                    )

        return expired

    def is_expired(self, stage) -> bool:
        """
        Check whether a stage has run longer than its timeout allows.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineTimeoutError:
                If stage is None or malformed
        """

        self._validate_stage(stage)

        elapsed_seconds = (datetime.now(timezone.utc) - stage.started_at).total_seconds()

        return elapsed_seconds >= stage.timeout_policy.timeout_seconds

    def remaining_time(self, stage) -> float:
        """
        Compute how many seconds remain before a stage times out.

        Returns:
            The number of seconds remaining, floored at zero once the
            stage has timed out

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineTimeoutError:
                If stage is None or malformed
        """

        self._validate_stage(stage)

        elapsed_seconds = (datetime.now(timezone.utc) - stage.started_at).total_seconds()

        return max(0.0, stage.timeout_policy.timeout_seconds - elapsed_seconds)

    def cancel(self, stage_id: str, reason: str = _DEFAULT_CANCELLATION_REASON) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineCancellationResult:
        """
        Cancel a stage and record why.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineTimeoutError:
                If stage_id is None or blank, the stage has already
                been marked complete(), or the stage has already been
                cancelled
        """

        self._validate_id(stage_id, "stage ID")

        with self._lock:
            if stage_id in self._completed:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineTimeoutError(
                    f"Cannot cancel stage ID {stage_id!r}: stage is already completed."
                )

            if stage_id in self._cancellations:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineTimeoutError(
                    f"Cannot cancel stage ID {stage_id!r}: stage is already cancelled."
                )

            result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineCancellationResult(
                stage_id=stage_id,
                cancelled=True,
                reason=reason,
            )

            self._cancellations[stage_id] = result

            return result

    def complete(self, stage_id: str) -> None:
        """
        Mark a stage as completed, making it ineligible for
        cancellation.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineTimeoutError:
                If stage_id is None or blank, or the stage has
                already been cancelled
        """

        self._validate_id(stage_id, "stage ID")

        with self._lock:
            if stage_id in self._cancellations:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineTimeoutError(
                    f"Cannot complete stage ID {stage_id!r}: stage is already cancelled."
                )

            self._completed.add(stage_id)

    def cancellation(self, stage_id: str):
        """
        Look up a stage's recorded cancellation, if any.

        Returns:
            The stage's cancellation result, or None if it has not
            been cancelled

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineTimeoutError:
                If stage_id is None or blank
        """

        self._validate_id(stage_id, "stage ID")

        with self._lock:
            return self._cancellations.get(stage_id)

    def _validate_stage(self, stage) -> None:
        if stage is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineTimeoutError(
                "Cannot operate on a None stage."
            )

        stage_id = getattr(stage, "stage_id", None)

        if stage_id is None or not str(stage_id).strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineTimeoutError(
                "Cannot operate on a stage with an empty or blank stage ID."
            )

        started_at = getattr(stage, "started_at", None)

        if started_at is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineTimeoutError(
                f"Cannot operate on stage ID {stage_id!r} with a None started_at."
            )

        timeout_policy = getattr(stage, "timeout_policy", None)

        if timeout_policy is None or not isinstance(timeout_policy, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineTimeoutPolicy):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineTimeoutError(
                f"Cannot operate on stage ID {stage_id!r}: timeout_policy must be a "
                "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineTimeoutPolicy."
            )

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineTimeoutError(
                f"Cannot operate with an empty or blank {label}."
            )
