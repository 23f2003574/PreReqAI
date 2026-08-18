import math

from datetime import (
    datetime,
    timezone,
)

from numbers import (
    Real,
)

from threading import (
    RLock,
)

from uuid import uuid4

from .execution_network_traffic_policy import (
    DIRECTION_INGRESS,
    DIRECTIONS,
)

from .execution_network_quota import (
    ExecutionNetworkQuota,
)

from .execution_network_quota_error import (
    ExecutionNetworkQuotaError,
)


class ExecutionNetworkQuotaService:
    """
    Prevents individual runtimes from monopolizing network bandwidth.

    Behavior:
    - configure() replaces a runtime's quota with a freshly built one
      and atomically clears any usage recorded under the previous
      configuration
    - consume() tracks ingress and egress usage independently against
      a rolling window that resets itself once window_seconds has
      elapsed since it started; it rejects an amount that would push
      the current window's usage past the active limit, but a
      disabled quota is never enforced
    - available() reports the remaining capacity in the current
      window for a direction, without mutating any stored usage; a
      disabled quota reports unlimited availability
    - reset() atomically zeroes both directions' usage for a runtime

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self):
        self._quotas_by_runtime = {}
        self._usage_by_runtime = {}
        self._lock = RLock()

    def configure(self, runtime_id: str, limits) -> ExecutionNetworkQuota:
        """
        Replace runtime_id's quota with one built from limits, an
        object exposing ingress_limit, egress_limit, window_seconds,
        and optionally enabled (default True) by item or attribute
        access.

        Raises:
            ExecutionNetworkQuotaError: If runtime_id is None or
                blank, or the resulting quota's fields are invalid
                (limits must be positive)
        """

        self._validate_text(runtime_id, "runtime ID")

        quota = ExecutionNetworkQuota(
            quota_id=str(uuid4()),
            runtime_id=runtime_id,
            ingress_limit=self._extract(limits, "ingress_limit"),
            egress_limit=self._extract(limits, "egress_limit"),
            window_seconds=self._extract(limits, "window_seconds"),
            enabled=self._extract(limits, "enabled", True),
        )

        with self._lock:
            self._quotas_by_runtime[runtime_id] = quota
            self._usage_by_runtime[runtime_id] = {}

        return quota

    def consume(self, runtime_id: str, direction: str, amount: float) -> float:
        """
        Consume amount of runtime_id's quota for direction, rolling
        the usage window over first if it has expired.

        Returns the remaining capacity for direction after consuming,
        or math.inf if the quota is disabled.

        Raises:
            ExecutionNetworkQuotaError: If runtime_id or direction is
                invalid, amount is not a positive number, no quota is
                configured for runtime_id, or amount would exceed the
                active quota
        """

        self._validate_text(runtime_id, "runtime ID")
        self._validate_direction(direction)
        self._validate_amount(amount)

        quota = self._resolve_quota(runtime_id)

        if not quota.enabled:
            return math.inf

        limit = quota.ingress_limit if direction == DIRECTION_INGRESS else quota.egress_limit

        with self._lock:
            used = self._roll_window(runtime_id, direction, quota)

            if used + amount > limit:
                raise ExecutionNetworkQuotaError(
                    f"Cannot consume {amount!r} of {direction} quota for runtime ID {runtime_id!r}: "
                    f"it would exceed the active limit of {limit!r} (already used {used!r})."
                )

            new_used = used + amount
            self._usage_by_runtime[runtime_id][direction] = (
                new_used,
                self._usage_by_runtime[runtime_id][direction][1],
            )

            return limit - new_used

    def available(self, runtime_id: str, direction: str) -> float:
        """
        The remaining capacity in the current window for runtime_id's
        direction. math.inf when the quota is disabled.

        Raises:
            ExecutionNetworkQuotaError: If runtime_id or direction is
                invalid, or no quota is configured for runtime_id
        """

        self._validate_text(runtime_id, "runtime ID")
        self._validate_direction(direction)

        quota = self._resolve_quota(runtime_id)

        if not quota.enabled:
            return math.inf

        limit = quota.ingress_limit if direction == DIRECTION_INGRESS else quota.egress_limit

        with self._lock:
            used = self._effective_usage(runtime_id, direction, quota)

        return limit - used

    def reset(self, runtime_id: str) -> None:
        """
        Atomically zero both directions' usage for runtime_id.

        Raises:
            ExecutionNetworkQuotaError: If runtime_id is None or
                blank, or no quota is configured for it
        """

        self._validate_text(runtime_id, "runtime ID")
        self._resolve_quota(runtime_id)

        with self._lock:
            self._usage_by_runtime[runtime_id] = {}

    def _roll_window(self, runtime_id: str, direction: str, quota: ExecutionNetworkQuota) -> float:
        now = datetime.now(timezone.utc)
        usage = self._usage_by_runtime.setdefault(runtime_id, {})
        used, window_started_at = usage.get(direction, (0.0, now))

        if (now - window_started_at).total_seconds() >= quota.window_seconds:
            used = 0.0
            window_started_at = now

        usage[direction] = (used, window_started_at)

        return used

    def _effective_usage(self, runtime_id: str, direction: str, quota: ExecutionNetworkQuota) -> float:
        usage = self._usage_by_runtime.get(runtime_id, {})

        if direction not in usage:
            return 0.0

        used, window_started_at = usage[direction]
        now = datetime.now(timezone.utc)

        if (now - window_started_at).total_seconds() >= quota.window_seconds:
            return 0.0

        return used

    def _resolve_quota(self, runtime_id: str) -> ExecutionNetworkQuota:
        quota = self._quotas_by_runtime.get(runtime_id)

        if quota is None:
            raise ExecutionNetworkQuotaError(f"No quota is configured for runtime ID {runtime_id!r}.")

        return quota

    @staticmethod
    def _extract(limits, key: str, default=None):
        try:
            return limits[key]
        except (TypeError, KeyError, IndexError):
            return getattr(limits, key, default)

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionNetworkQuotaError(f"Cannot use an empty or blank {field_name}.")

    @staticmethod
    def _validate_direction(direction: str) -> None:
        if direction not in DIRECTIONS:
            raise ExecutionNetworkQuotaError(f"Cannot use an unknown direction: {direction!r}.")

    @staticmethod
    def _validate_amount(amount) -> None:
        if amount is None or isinstance(amount, bool) or not isinstance(amount, Real) or amount <= 0:
            raise ExecutionNetworkQuotaError(f"Cannot use a non-positive amount: {amount!r}.")
