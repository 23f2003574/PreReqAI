from datetime import (
    datetime,
    timezone,
)

from .execution_runtime_health import (
    ExecutionRuntimeHealth,
    STATUS_DEGRADED,
    STATUS_FAILED,
    STATUS_HEALTHY,
)

from .execution_runtime_health_error import (
    ExecutionRuntimeHealthError,
)

STATE_FAILED = "FAILED"

ISSUE_RUNTIME_FAILED = "runtime failed"

ISSUE_STALE_HEARTBEAT = "stale heartbeat"

ISSUE_TIMEOUT_EXCEEDED = "timeout exceeded"

ISSUE_RESOURCE_LEAK = "resource leak"

FAILING_ISSUES = (ISSUE_RUNTIME_FAILED, ISSUE_TIMEOUT_EXCEEDED, ISSUE_RESOURCE_LEAK)

DEFAULT_HEARTBEAT_TIMEOUT_SECONDS = 30


class ExecutionRuntimeHealthService:
    """
    Combines heartbeat, timeout, resource, and lifecycle signals into
    one runtime health state.

    Composes with existing services for each signal (duck-typed to
    what each already exposes):
        state_service: state(runtime_id) -> object with .state
            (ExecutionRuntimeStateService)
        heartbeat_service: healthy(runtime_id, timeout) -> bool
            (ExecutionRuntimeHeartbeatService)
        timeout_service: check(runtime_id) -> bool; expired() -> tuple
            of runtime IDs (ExecutionRuntimeTimeoutService)
        resource_service: leaked() -> tuple of objects with
            .runtime_id (ExecutionRuntimeResourceService)

    Behavior:
    - check() computes a fresh ExecutionRuntimeHealth snapshot by
      reading, never writing to, every composed service: a FAILED
      lifecycle state, an exceeded timeout, or a leaked resource each
      make the runtime FAILED; failing that, a stale heartbeat makes
      it DEGRADED; otherwise it is HEALTHY. The same signals always
      produce the same status (deterministic)
    - healthy() and issues() both derive from a fresh check()
    - unhealthy() sweeps every runtime any composed service currently
      flags (stale, timed out, or leaking) and reports a fresh
      snapshot for each one that is not HEALTHY

    The service performs no mutation of its own or of any composed
    service; every method here is read-only.
    """

    def __init__(
        self,
        state_service,
        heartbeat_service,
        timeout_service,
        resource_service,
        heartbeat_timeout_seconds: float = DEFAULT_HEARTBEAT_TIMEOUT_SECONDS,
    ):
        self._state_service = state_service
        self._heartbeat_service = heartbeat_service
        self._timeout_service = timeout_service
        self._resource_service = resource_service
        self._heartbeat_timeout_seconds = heartbeat_timeout_seconds

    def check(self, runtime_id: str) -> ExecutionRuntimeHealth:
        """
        Compute a fresh combined health snapshot for runtime_id.

        Raises:
            ExecutionRuntimeHealthError: If runtime_id is None or
                blank, or runtime_id is unknown to the state service
        """

        self._validate_text(runtime_id, "runtime ID")

        current_state = self._current_state(runtime_id)

        issues = []

        if current_state == STATE_FAILED:
            issues.append(ISSUE_RUNTIME_FAILED)

        if not self._heartbeat_service.healthy(runtime_id, self._heartbeat_timeout_seconds):
            issues.append(ISSUE_STALE_HEARTBEAT)

        if self._is_timed_out(runtime_id):
            issues.append(ISSUE_TIMEOUT_EXCEEDED)

        if self._has_leaked_resources(runtime_id):
            issues.append(ISSUE_RESOURCE_LEAK)

        status = self._status_for(issues)

        return ExecutionRuntimeHealth(
            runtime_id=runtime_id,
            status=status,
            issues=tuple(issues),
            checked_at=datetime.now(timezone.utc),
        )

    def healthy(self, runtime_id: str) -> bool:
        """
        Whether runtime_id is currently HEALTHY.
        """

        return self.check(runtime_id).status == STATUS_HEALTHY

    def issues(self, runtime_id: str) -> tuple:
        """
        The specific problems found for runtime_id right now.
        """

        return self.check(runtime_id).issues

    def unhealthy(self) -> tuple:
        """
        A fresh health snapshot for every runtime currently flagged
        by any composed service (stale heartbeat, timed out, or
        leaking resources) that is not HEALTHY.
        """

        runtime_ids = set(self._heartbeat_service.stale())
        runtime_ids.update(self._timeout_service.expired())
        runtime_ids.update(resource.runtime_id for resource in self._resource_service.leaked())

        snapshots = (self.check(runtime_id) for runtime_id in runtime_ids)

        return tuple(snapshot for snapshot in snapshots if snapshot.status != STATUS_HEALTHY)

    def _is_timed_out(self, runtime_id: str) -> bool:
        try:
            return not self._timeout_service.check(runtime_id)
        except Exception:
            return False

    def _has_leaked_resources(self, runtime_id: str) -> bool:
        return any(resource.runtime_id == runtime_id for resource in self._resource_service.leaked())

    def _current_state(self, runtime_id: str) -> str:
        try:
            return self._state_service.state(runtime_id).state
        except Exception as error:
            raise ExecutionRuntimeHealthError(
                f"Cannot resolve runtime ID {runtime_id!r}: it is unknown."
            ) from error

    @staticmethod
    def _status_for(issues) -> str:
        if any(issue in FAILING_ISSUES for issue in issues):
            return STATUS_FAILED

        if ISSUE_STALE_HEARTBEAT in issues:
            return STATUS_DEGRADED

        return STATUS_HEALTHY

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionRuntimeHealthError(f"Cannot use an empty or blank {field_name}.")
