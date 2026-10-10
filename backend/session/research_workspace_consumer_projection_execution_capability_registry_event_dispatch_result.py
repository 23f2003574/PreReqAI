from dataclasses import (
    dataclass,
)

from typing import (
    Any,
)


@dataclass(frozen=True)
class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventDispatchResult:
    """
    Immutable outcome of a completed consumer projection execution
    capability registry event dispatch.

    Captures dispatch metadata only - it does not perform
    dispatching, retries, logging, or error handling.

    Attributes:
        event: The event that was dispatched
        subscriber_count: The number of subscribers dispatch was
            attempted against
        successful_dispatch_count: The number of subscribers
            successfully handled the event
        completed: True when successful_dispatch_count equals
            subscriber_count
    """

    event: Any

    subscriber_count: int

    successful_dispatch_count: int

    completed: bool
