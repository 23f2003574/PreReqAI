from dataclasses import (
    replace,
)

from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from uuid import uuid4

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_pipeline_queue_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQueueError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_pipeline_queue_item import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQueueItem,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_pipeline_queue_statistics import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQueueStatistics,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_pipeline_queue_item_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQueueItemStatus,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQueueService:
    """
    Schedules consumer projection execution capability registry event
    subscription lifecycle policy profile binding workspace execution
    pipelines through a managed queue, so at most a configured number
    run at once.

    The service's responsibility is scheduling and bookkeeping, not
    running a pipeline itself. It does NOT execute pipelines; whoever
    runs them (for example, a consumer projection execution
    capability registry event subscription lifecycle policy profile
    binding workspace execution pipeline service) is expected to call
    dequeue() to obtain the next pipeline ID to run, and complete()
    once it finishes.

    Behavior:
    - dequeue() and peek() select the queued item with the highest
      priority; items sharing a priority are selected in the order
      they were enqueued (FIFO)
    - dequeue() returns None when the number of currently RUNNING
      items has reached the configured concurrency limit, or when
      nothing is queued
    - A pipeline ID with a QUEUED or RUNNING item cannot be enqueued
      again until that item completes

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, concurrency_limit: int = 1):
        """
        Args:
            concurrency_limit: The maximum number of items dequeue()
                will allow to be RUNNING at once

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQueueError:
                If concurrency_limit is not a positive integer
        """

        if (
            concurrency_limit is None
            or isinstance(concurrency_limit, bool)
            or not isinstance(concurrency_limit, int)
            or concurrency_limit < 1
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQueueError(
                "Cannot initialize a pipeline queue service with a concurrency_limit that is not a positive "
                "integer."
            )

        self._concurrency_limit = concurrency_limit
        self._items = {}
        self._lock = RLock()

    def enqueue(self, pipeline_id: str, priority: int) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQueueItem:
        """
        Add a pipeline to the queue.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQueueError:
                If pipeline_id is None or blank, priority is not a
                non-negative integer, or pipeline_id already has a
                queued or running item
        """

        self._validate_id(pipeline_id, "pipeline ID")

        with self._lock:
            for existing in self._items.values():
                if existing.pipeline_id == pipeline_id and existing.status in (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQueueItemStatus.QUEUED,
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQueueItemStatus.RUNNING,
                ):
                    raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQueueError(
                        f"Cannot enqueue pipeline ID {pipeline_id!r}: it already has a "
                        f"{existing.status.value} queue item."
                    )

            item = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQueueItem(
                queue_item_id=str(uuid4()),
                pipeline_id=pipeline_id,
                priority=priority,
                queued_at=datetime.now(timezone.utc),
                status=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQueueItemStatus.QUEUED,
            )

            self._items[item.queue_item_id] = item

            return item

    def dequeue(self):
        """
        Select and start the next eligible queued item, in
        priority-first, then FIFO, order.

        Returns:
            The item, now RUNNING, or None if nothing is eligible to
            start: either nothing is queued, or the concurrency limit
            has been reached
        """

        with self._lock:
            running_count = sum(1 for item in self._items.values() if item.status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQueueItemStatus.RUNNING)

            if running_count >= self._concurrency_limit:
                return None

            next_item = self._next_queued()

            if next_item is None:
                return None

            running = replace(next_item, status=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQueueItemStatus.RUNNING)
            self._items[next_item.queue_item_id] = running

            return running

    def peek(self):
        """
        Look at the next eligible queued item without starting it.

        Returns:
            The item that dequeue() would select next, or None if
            nothing is queued
        """

        with self._lock:
            return self._next_queued()

    def complete(self, queue_item_id: str, successful: bool = True) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQueueItem:
        """
        Mark a queue item as finished.

        Args:
            queue_item_id: The item to complete
            successful: Whether the pipeline finished successfully;
                determines whether the item becomes COMPLETED or
                FAILED

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQueueError:
                If queue_item_id is None or blank, or no item is
                registered under it
        """

        self._validate_id(queue_item_id, "queue item ID")

        with self._lock:
            item = self._items.get(queue_item_id)

            if item is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQueueError(
                    f"No pipeline queue item is registered under queue item ID {queue_item_id!r}."
                )

            finished = replace(
                item,
                status=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQueueItemStatus.COMPLETED if successful else ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQueueItemStatus.FAILED,
            )

            self._items[queue_item_id] = finished

            return finished

    def statistics(self) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQueueStatistics:
        """
        Count queue items by state.
        """

        with self._lock:
            counts = {status: 0 for status in ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQueueItemStatus}

            for item in self._items.values():
                counts[item.status] += 1

            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQueueStatistics(
                queued=counts[ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQueueItemStatus.QUEUED],
                running=counts[ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQueueItemStatus.RUNNING],
                completed=counts[ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQueueItemStatus.COMPLETED],
                failed=counts[ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQueueItemStatus.FAILED],
            )

    def clear_completed(self) -> int:
        """
        Remove every COMPLETED or FAILED item from the queue.

        Returns:
            The number of items removed
        """

        with self._lock:
            to_remove = [
                queue_item_id
                for queue_item_id, item in self._items.items()
                if item.status in (ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQueueItemStatus.COMPLETED, ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQueueItemStatus.FAILED)
            ]

            for queue_item_id in to_remove:
                del self._items[queue_item_id]

            return len(to_remove)

    def _next_queued(self):
        queued = [item for item in self._items.values() if item.status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQueueItemStatus.QUEUED]

        if not queued:
            return None

        return min(queued, key=lambda item: (-item.priority, item.queued_at))

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspacePipelineQueueError(
                f"Cannot operate with an empty or blank {label}."
            )
