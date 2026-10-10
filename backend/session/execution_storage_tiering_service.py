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

from .execution_storage_integrity_check import (
    STATUS_OK,
)

from .execution_storage_tier import (
    ExecutionStorageTier,
    TIER_COLD,
    TIER_HOT,
    TIER_WARM,
    TIERS,
)

from .execution_storage_tier_error import (
    ExecutionStorageTierError,
)

DEFAULT_WARM_AFTER_SECONDS = 3600

DEFAULT_COLD_AFTER_SECONDS = 86400


class ExecutionStorageTieringService:
    """
    Automatically classifies storage into HOT, WARM, and COLD tiers
    based on access patterns.

    Composes with:
    - an existing storage volume service (anything exposing
      `for_scope(scope_id) -> tuple of objects with .volume_id`),
      used to enumerate a scope's resources for candidates()
    - an existing storage mount service (anything exposing
      `volume_mounts(resource_id) -> tuple`, matching
      ExecutionStorageMountService), used to confirm a resource holds
      no active mounts before it can leave HOT
    - an existing storage integrity service (anything exposing
      `check(resource_id) -> object with .status`, matching
      ExecutionStorageIntegrityService), used to refuse to evaluate
      or transition a corrupted resource
    - an access tracking service (anything exposing
      `last_accessed(resource_id) -> datetime`), used as the source
      of truth for how recently a resource was used

    Behavior:
    - evaluate() deterministically recommends a resource's tier: HOT
      while it holds an active mount or was accessed within
      warm_after_seconds, WARM once older than that but within
      cold_after_seconds, COLD beyond that; it never evaluates a
      corrupted resource
    - transition() explicitly moves a resource to a tier, recording a
      new snapshot; it refuses a corrupted resource, and refuses to
      move a resource with active mounts to anything but HOT -- a
      transition only ever happens because this was called, never as
      a side effect of evaluate()
    - tier() reports a resource's current (most recently transitioned
      to) tier
    - candidates() reports the resources under a scope whose evaluated
      tier currently differs from their last recorded tier
    - history() reports every transition ever recorded for a
      resource, oldest first

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(
        self,
        volume_service,
        mount_service,
        integrity_service,
        access_service,
        warm_after_seconds=DEFAULT_WARM_AFTER_SECONDS,
        cold_after_seconds=DEFAULT_COLD_AFTER_SECONDS,
    ):
        if not self._is_positive(warm_after_seconds) or not self._is_positive(cold_after_seconds):
            raise ExecutionStorageTierError(
                "Cannot use non-positive warm_after_seconds or cold_after_seconds."
            )

        if cold_after_seconds <= warm_after_seconds:
            raise ExecutionStorageTierError(
                "Cannot use a cold_after_seconds that does not exceed warm_after_seconds."
            )

        self._volume_service = volume_service
        self._mount_service = mount_service
        self._integrity_service = integrity_service
        self._access_service = access_service
        self._warm_after_seconds = warm_after_seconds
        self._cold_after_seconds = cold_after_seconds
        self._current_by_resource = {}
        self._history_by_resource = {}
        self._lock = RLock()

    def evaluate(self, resource_id: str) -> str:
        """
        The tier resource_id currently warrants, without transitioning
        it.

        Raises:
            ExecutionStorageTierError: If resource_id is None or
                blank, it is unknown, or it is corrupted
        """

        self._validate_text(resource_id, "resource ID")

        if self._is_corrupt(resource_id):
            raise ExecutionStorageTierError(
                f"Cannot evaluate resource ID {resource_id!r}: it is corrupted."
            )

        if self._has_active_mounts(resource_id):
            return TIER_HOT

        last_accessed = self._safe_call(self._access_service.last_accessed, resource_id)
        age = (datetime.now(timezone.utc) - last_accessed).total_seconds()

        if age < self._warm_after_seconds:
            return TIER_HOT

        if age < self._cold_after_seconds:
            return TIER_WARM

        return TIER_COLD

    def transition(self, resource_id: str, tier: str) -> ExecutionStorageTier:
        """
        Explicitly move resource_id to tier, recording a new
        transition.

        Raises:
            ExecutionStorageTierError: If resource_id is None or
                blank, tier is not one of TIERS, resource_id is
                unknown, it is corrupted, or it holds active mounts
                and tier is not HOT
        """

        self._validate_text(resource_id, "resource ID")
        self._validate_tier(tier)

        if self._is_corrupt(resource_id):
            raise ExecutionStorageTierError(
                f"Cannot transition resource ID {resource_id!r}: it is corrupted."
            )

        if tier != TIER_HOT and self._has_active_mounts(resource_id):
            raise ExecutionStorageTierError(
                f"Cannot transition resource ID {resource_id!r} to {tier!r}: it holds active "
                f"mounts and must remain HOT."
            )

        last_accessed = self._safe_call(self._access_service.last_accessed, resource_id)

        record = ExecutionStorageTier(
            tier_id=str(uuid4()),
            resource_id=resource_id,
            tier=tier,
            last_accessed=last_accessed,
            transitioned_at=datetime.now(timezone.utc),
        )

        with self._lock:
            self._current_by_resource[resource_id] = record
            self._history_by_resource.setdefault(resource_id, []).append(record)

        return record

    def tier(self, resource_id: str) -> str:
        """
        The current (most recently transitioned to) tier of
        resource_id.

        Raises:
            ExecutionStorageTierError: If resource_id is None or
                blank, or it has never been transitioned
        """

        self._validate_text(resource_id, "resource ID")

        with self._lock:
            current = self._current_by_resource.get(resource_id)

        if current is None:
            raise ExecutionStorageTierError(f"Resource ID {resource_id!r} has never been tiered.")

        return current.tier

    def candidates(self, scope_id: str) -> tuple:
        """
        The resources under scope_id whose evaluated tier currently
        differs from their last recorded tier, including resources
        never yet tiered. Corrupted resources are skipped, never
        surfaced as candidates.

        Raises:
            ExecutionStorageTierError: If scope_id is None or blank
        """

        self._validate_text(scope_id, "scope ID")

        volumes = self._safe_call(self._volume_service.for_scope, scope_id)

        result = []

        for volume in volumes:
            try:
                recommended = self.evaluate(volume.volume_id)
            except ExecutionStorageTierError:
                continue

            with self._lock:
                current = self._current_by_resource.get(volume.volume_id)

            current_tier = current.tier if current is not None else None

            if recommended != current_tier:
                result.append(volume.volume_id)

        return tuple(result)

    def history(self, resource_id: str) -> tuple:
        """
        Every transition ever recorded for resource_id, oldest first.
        """

        self._validate_text(resource_id, "resource ID")

        with self._lock:
            return tuple(self._history_by_resource.get(resource_id, ()))

    def _is_corrupt(self, resource_id: str) -> bool:
        try:
            check = self._integrity_service.check(resource_id)
        except Exception:
            return False

        return check.status != STATUS_OK

    def _has_active_mounts(self, resource_id: str) -> bool:
        mounts = self._safe_call(self._mount_service.volume_mounts, resource_id)

        return len(mounts) > 0

    @staticmethod
    def _safe_call(fn, *args):
        try:
            return fn(*args)
        except Exception as error:
            raise ExecutionStorageTierError(f"Cannot resolve: {error}") from error

    @staticmethod
    def _is_positive(value) -> bool:
        return value is not None and not isinstance(value, bool) and isinstance(value, Real) and value > 0

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionStorageTierError(f"Cannot use an empty or blank {field_name}.")

    @staticmethod
    def _validate_tier(tier: str) -> None:
        if tier not in TIERS:
            raise ExecutionStorageTierError(f"Cannot use an unknown tier: {tier!r}.")
