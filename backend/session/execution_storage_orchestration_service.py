from threading import (
    RLock,
)

from uuid import uuid4

from .execution_storage_mount import (
    MODE_READ_WRITE,
)

from .execution_storage_integrity_check import (
    STATUS_OK,
)

from .execution_storage_decision import (
    ExecutionStorageDecision,
)

from .execution_storage_decision_error import (
    ExecutionStorageDecisionError,
)


class ExecutionStorageOrchestrationService:
    """
    Unifies volume allocation, mounts, snapshots, replication,
    integrity, retention, tiering, migration, and failover into one
    storage decision pipeline.

    Composes with existing storage components:
    - a quota service (`can_allocate`, `allocate`, `release`, matching
      ExecutionStorageQuotaService), keyed by runtime_id in place of a
      scope_id
    - a volume service (`create`, `detach`, `delete`, matching
      ExecutionStorageVolumeService)
    - a mount service (`mount`, `unmount`, `volume_mounts`, matching
      ExecutionStorageMountService)
    - an integrity service (`check(volume_id) -> object with
      .status`, matching ExecutionStorageIntegrityService)
    - a retention service (`eligible(resource_id) -> bool`, matching
      ExecutionStorageRetentionService)
    - a tiering service (`evaluate(resource_id) -> str`, matching
      ExecutionStorageTieringService)
    - a failover service (`select`, `execute`, matching
      ExecutionStorageFailoverService)

    This service treats runtime_id as the quota and volume scope: a
    provisioned volume's scope_id is its provisioning runtime_id.

    Behavior:
    - provision() checks quota before creating anything; a volume is
      only ever created once capacity is confirmed
    - mount() attempts a mount for the runtime and records exactly
      one decision, allowed or not, rather than raising for a
      rejected mount
    - evaluate() verifies integrity first -- an integrity failure is
      never overridden -- then, informed by the volume's retention and
      tiering state, selects a verified storage target
    - failover() re-runs failover selection and records its outcome
    - release() unmounts, detaches, releases quota, and deletes a
      volume, best-effort, and always records the release
    - decision() reports the most recent decision recorded for a
      volume

    Every action but provision()'s quota gate produces exactly one new
    decision, deterministic in the current state of the composed
    components.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(
        self,
        quota_service,
        volume_service,
        mount_service,
        integrity_service,
        retention_service,
        tiering_service,
        failover_service,
    ):
        self._quota_service = quota_service
        self._volume_service = volume_service
        self._mount_service = mount_service
        self._integrity_service = integrity_service
        self._retention_service = retention_service
        self._tiering_service = tiering_service
        self._failover_service = failover_service
        self._decisions_by_volume = {}
        self._runtime_by_volume = {}
        self._size_by_volume = {}
        self._lock = RLock()

    def provision(self, runtime_id: str, size: float) -> ExecutionStorageDecision:
        """
        Provision a new volume of size for runtime_id, after
        confirming quota allows it.

        Raises:
            ExecutionStorageDecisionError: If runtime_id is None or
                blank, or runtime_id's quota does not have room for
                size
        """

        self._validate_text(runtime_id, "runtime ID")

        if not self._can_allocate(runtime_id, size):
            raise ExecutionStorageDecisionError(
                f"Cannot provision a volume for runtime ID {runtime_id!r}: quota does not have "
                f"room for size {size!r}."
            )

        self._safe_call(self._quota_service.allocate, runtime_id, size)
        volume = self._safe_call(self._volume_service.create, runtime_id, size)

        with self._lock:
            self._runtime_by_volume[volume.volume_id] = runtime_id
            self._size_by_volume[volume.volume_id] = size

        return self._record(runtime_id, volume.volume_id, target=None, allowed=True, reason="provisioned")

    def mount(self, runtime_id: str, volume_id: str) -> ExecutionStorageDecision:
        """
        Attempt to mount volume_id for runtime_id, recording exactly
        one decision either way.

        Raises:
            ExecutionStorageDecisionError: If runtime_id or volume_id
                is None or blank
        """

        self._validate_text(runtime_id, "runtime ID")
        self._validate_text(volume_id, "volume ID")

        with self._lock:
            self._runtime_by_volume[volume_id] = runtime_id

        try:
            self._mount_service.mount(volume_id, runtime_id, f"/mnt/{volume_id}", MODE_READ_WRITE)
        except Exception as error:
            return self._record(
                runtime_id, volume_id, target=None, allowed=False, reason=f"mount rejected: {error}"
            )

        return self._record(runtime_id, volume_id, target=None, allowed=True, reason="mounted")

    def evaluate(self, volume_id: str) -> ExecutionStorageDecision:
        """
        Evaluate volume_id: verify its integrity, then select a
        verified storage target, informed by its retention and
        tiering state.

        Raises:
            ExecutionStorageDecisionError: If volume_id is None or
                blank, or it is unknown to this orchestration service
        """

        runtime_id = self._require_runtime(volume_id)

        if not self._is_healthy(volume_id):
            return self._record(
                runtime_id, volume_id, target=None, allowed=False, reason="integrity check failed"
            )

        target = self._safe_select(volume_id)

        if target is None:
            return self._record(
                runtime_id, volume_id, target=None, allowed=False, reason="no verified target available"
            )

        posture = self._retention_tiering_posture(volume_id)

        return self._record(
            runtime_id, volume_id, target=target, allowed=True, reason=f"verified target selected ({posture})"
        )

    def failover(self, volume_id: str) -> ExecutionStorageDecision:
        """
        Re-run failover selection for volume_id and record its
        outcome.

        Raises:
            ExecutionStorageDecisionError: If volume_id is None or
                blank, or it is unknown to this orchestration service
        """

        runtime_id = self._require_runtime(volume_id)

        try:
            result = self._failover_service.execute(volume_id)
        except Exception as error:
            return self._record(
                runtime_id, volume_id, target=None, allowed=False, reason=f"failover unavailable: {error}"
            )

        if result.selected_target is None:
            return self._record(
                runtime_id, volume_id, target=None, allowed=False, reason="no valid target remains"
            )

        return self._record(
            runtime_id,
            volume_id,
            target=result.selected_target,
            allowed=True,
            reason=f"failed over to {result.selected_target}",
        )

    def release(self, volume_id: str) -> ExecutionStorageDecision:
        """
        Unmount, detach, release quota for, and delete volume_id,
        best-effort, and record the release.

        Raises:
            ExecutionStorageDecisionError: If volume_id is None or
                blank, or it is unknown to this orchestration service
        """

        runtime_id = self._require_runtime(volume_id)

        for mount_record in self._safe_default(self._mount_service.volume_mounts, volume_id, ()):
            self._ignore_errors(self._mount_service.unmount, mount_record.mount_id)

        self._ignore_errors(self._volume_service.detach, volume_id, runtime_id)

        with self._lock:
            size = self._size_by_volume.pop(volume_id, None)

        if size is not None:
            self._ignore_errors(self._quota_service.release, runtime_id, size)

        self._ignore_errors(self._volume_service.delete, volume_id)

        return self._record(runtime_id, volume_id, target=None, allowed=True, reason="released")

    def decision(self, volume_id: str) -> ExecutionStorageDecision:
        """
        The most recent decision recorded for volume_id.

        Raises:
            ExecutionStorageDecisionError: If volume_id is None or
                blank, or no decision has been recorded for it
        """

        self._validate_text(volume_id, "volume ID")

        with self._lock:
            record = self._decisions_by_volume.get(volume_id)

        if record is None:
            raise ExecutionStorageDecisionError(f"No decision has been recorded for volume ID {volume_id!r}.")

        return record

    def _record(
        self, runtime_id: str, volume_id: str, target, allowed: bool, reason: str
    ) -> ExecutionStorageDecision:
        record = ExecutionStorageDecision(
            decision_id=str(uuid4()),
            runtime_id=runtime_id,
            volume_id=volume_id,
            target=target,
            allowed=allowed,
            reason=reason,
        )

        with self._lock:
            self._decisions_by_volume[volume_id] = record

        return record

    def _can_allocate(self, runtime_id: str, size) -> bool:
        try:
            return bool(self._quota_service.can_allocate(runtime_id, size))
        except Exception:
            return False

    def _is_healthy(self, volume_id: str) -> bool:
        try:
            check = self._integrity_service.check(volume_id)
        except Exception:
            return False

        return check.status == STATUS_OK

    def _safe_select(self, volume_id: str):
        try:
            return self._failover_service.select(volume_id)
        except Exception:
            return None

    def _retention_tiering_posture(self, volume_id: str) -> str:
        try:
            eligible = bool(self._retention_service.eligible(volume_id))
        except Exception:
            eligible = None

        try:
            recommended_tier = self._tiering_service.evaluate(volume_id)
        except Exception:
            recommended_tier = None

        retention_label = "eligible" if eligible else "protected" if eligible is not None else "unknown"

        return f"retention {retention_label}, tier {recommended_tier or 'unknown'}"

    def _require_runtime(self, volume_id: str) -> str:
        self._validate_text(volume_id, "volume ID")

        with self._lock:
            runtime_id = self._runtime_by_volume.get(volume_id)

        if runtime_id is None:
            raise ExecutionStorageDecisionError(f"Volume ID {volume_id!r} is unknown to this orchestration service.")

        return runtime_id

    @staticmethod
    def _safe_call(fn, *args):
        try:
            return fn(*args)
        except Exception as error:
            raise ExecutionStorageDecisionError(f"Cannot resolve: {error}") from error

    @staticmethod
    def _safe_default(fn, arg, default):
        try:
            return fn(arg)
        except Exception:
            return default

    @staticmethod
    def _ignore_errors(fn, *args):
        try:
            fn(*args)
        except Exception:
            pass

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionStorageDecisionError(f"Cannot use an empty or blank {field_name}.")
