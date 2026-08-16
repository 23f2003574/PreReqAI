from dataclasses import (
    dataclass,
)

from .execution_concurrency_error import (
    ExecutionConcurrencyError,
)


@dataclass(frozen=True)
class ExecutionConcurrencyLimit:
    """
    Immutable record of how many execution jobs may run at once
    within a scope (for example, a workspace).

    The limit is a value object only. It performs no capacity
    tracking of its own; registering a limit and acquiring or
    releasing capacity against it is the responsibility of an
    execution concurrency service.

    Attributes:
        limit_id: The limit's unique identifier
        scope_id: The scope this limit governs
        max_running: The maximum number of jobs allowed to run at
            once within the scope. Must be at least 1
        enabled: Whether the limit is currently in effect. A disabled
            limit never allows a new job to start
    """

    limit_id: str

    scope_id: str

    max_running: int

    enabled: bool = True

    def __post_init__(self):
        self._require_text(self.limit_id, "limit ID")
        self._require_text(self.scope_id, "scope ID")

        if not isinstance(self.max_running, int) or isinstance(self.max_running, bool):
            raise ExecutionConcurrencyError(
                "Cannot build an execution concurrency limit with a non-int max_running."
            )

        if self.max_running < 1:
            raise ExecutionConcurrencyError(
                "Cannot build an execution concurrency limit with a max_running below 1."
            )

        if not isinstance(self.enabled, bool):
            raise ExecutionConcurrencyError(
                "Cannot build an execution concurrency limit with a non-bool enabled."
            )

    @staticmethod
    def _require_text(value, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionConcurrencyError(
                f"Cannot build an execution concurrency limit with an empty or blank {field_name}."
            )
