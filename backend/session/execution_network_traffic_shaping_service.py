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
    DIRECTIONS,
)

from .execution_network_traffic_shaper import (
    ExecutionNetworkTrafficShaper,
)

from .execution_network_traffic_shaper_error import (
    ExecutionNetworkTrafficShaperError,
)


class ExecutionNetworkTrafficShapingService:
    """
    Controls runtime traffic rates instead of only enforcing total
    quotas.

    Each (runtime_id, direction) pair gets its own token bucket,
    capped at burst_limit and refilled continuously at rate_limit
    tokens per second.

    Behavior:
    - configure() replaces a (runtime_id, direction) pair's shaper
      and resets its bucket to full (burst_limit tokens)
    - allow() refills the bucket for elapsed time first, then admits
      amount only if enough tokens are available, deducting them;
      a disabled shaper always allows traffic without deducting
      anything
    - remaining() reports the bucket's current tokens after refilling
      for elapsed time, without deducting; math.inf for a disabled
      shaper
    - reset() refills every direction configured for a runtime back
      to full capacity

    Directions are tracked independently: consuming one direction's
    bucket never affects the other's.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self):
        self._shapers_by_key = {}
        self._buckets_by_key = {}
        self._lock = RLock()

    def configure(
        self, runtime_id: str, direction: str, rate: float, burst: float, enabled: bool = True
    ) -> ExecutionNetworkTrafficShaper:
        """
        Replace the shaper for (runtime_id, direction) and reset its
        bucket to full capacity. A disabled shaper (enabled=False)
        is tracked but never enforced by allow() or remaining().

        Raises:
            ExecutionNetworkTrafficShaperError: If runtime_id is None
                or blank, direction is not one of DIRECTIONS, or rate
                or burst is not a positive number
        """

        self._validate_text(runtime_id, "runtime ID")
        self._validate_direction(direction)

        shaper = ExecutionNetworkTrafficShaper(
            shaper_id=str(uuid4()),
            runtime_id=runtime_id,
            direction=direction,
            rate_limit=rate,
            burst_limit=burst,
            enabled=enabled,
        )

        key = (runtime_id, direction)

        with self._lock:
            self._shapers_by_key[key] = shaper
            self._buckets_by_key[key] = (burst, datetime.now(timezone.utc))

        return shaper

    def allow(self, runtime_id: str, direction: str, amount: float) -> bool:
        """
        Whether amount of traffic is currently allowed for
        (runtime_id, direction); if so, deducts it from the bucket.
        Always True for a disabled shaper.

        Raises:
            ExecutionNetworkTrafficShaperError: If runtime_id is None
                or blank, direction is not one of DIRECTIONS, amount
                is not a positive number, or no shaper is configured
                for the pair
        """

        self._validate_text(runtime_id, "runtime ID")
        self._validate_direction(direction)
        self._validate_amount(amount)

        key = (runtime_id, direction)
        shaper = self._resolve_shaper(key)

        if not shaper.enabled:
            return True

        with self._lock:
            tokens = self._refill(key, shaper)

            if tokens < amount:
                return False

            self._buckets_by_key[key] = (tokens - amount, self._buckets_by_key[key][1])

            return True

    def remaining(self, runtime_id: str, direction: str) -> float:
        """
        The bucket's current tokens for (runtime_id, direction),
        after refilling for elapsed time. math.inf when the shaper
        is disabled.

        Raises:
            ExecutionNetworkTrafficShaperError: If runtime_id is None
                or blank, direction is not one of DIRECTIONS, or no
                shaper is configured for the pair
        """

        self._validate_text(runtime_id, "runtime ID")
        self._validate_direction(direction)

        key = (runtime_id, direction)
        shaper = self._resolve_shaper(key)

        if not shaper.enabled:
            return math.inf

        with self._lock:
            return self._peek(key, shaper)

    def reset(self, runtime_id: str) -> None:
        """
        Refill every direction configured for runtime_id back to
        full capacity.

        Raises:
            ExecutionNetworkTrafficShaperError: If runtime_id is None
                or blank, or no shaper is configured for it
        """

        self._validate_text(runtime_id, "runtime ID")

        with self._lock:
            keys = [key for key in self._shapers_by_key if key[0] == runtime_id]

            if not keys:
                raise ExecutionNetworkTrafficShaperError(
                    f"No traffic shaper is configured for runtime ID {runtime_id!r}."
                )

            now = datetime.now(timezone.utc)

            for key in keys:
                self._buckets_by_key[key] = (self._shapers_by_key[key].burst_limit, now)

    def _refill(self, key, shaper: ExecutionNetworkTrafficShaper) -> float:
        tokens, last_refill = self._buckets_by_key[key]
        now = datetime.now(timezone.utc)
        elapsed = (now - last_refill).total_seconds()
        tokens = min(shaper.burst_limit, tokens + elapsed * shaper.rate_limit)
        self._buckets_by_key[key] = (tokens, now)

        return tokens

    def _peek(self, key, shaper: ExecutionNetworkTrafficShaper) -> float:
        tokens, last_refill = self._buckets_by_key[key]
        elapsed = (datetime.now(timezone.utc) - last_refill).total_seconds()

        return min(shaper.burst_limit, tokens + elapsed * shaper.rate_limit)

    def _resolve_shaper(self, key) -> ExecutionNetworkTrafficShaper:
        shaper = self._shapers_by_key.get(key)

        if shaper is None:
            raise ExecutionNetworkTrafficShaperError(
                f"No traffic shaper is configured for runtime ID {key[0]!r} and direction "
                f"{key[1]!r}."
            )

        return shaper

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionNetworkTrafficShaperError(f"Cannot use an empty or blank {field_name}.")

    @staticmethod
    def _validate_direction(direction: str) -> None:
        if direction not in DIRECTIONS:
            raise ExecutionNetworkTrafficShaperError(f"Cannot use an unknown direction: {direction!r}.")

    @staticmethod
    def _validate_amount(amount) -> None:
        if amount is None or isinstance(amount, bool) or not isinstance(amount, Real) or amount <= 0:
            raise ExecutionNetworkTrafficShaperError(f"Cannot use a non-positive amount: {amount!r}.")
