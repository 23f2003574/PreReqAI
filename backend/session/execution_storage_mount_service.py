from threading import (
    RLock,
)

from uuid import uuid4

from .execution_storage_volume import (
    STATUS_AVAILABLE,
)

from .execution_storage_mount import (
    ExecutionStorageMount,
    MODE_READ_WRITE,
    MODES,
)

from .execution_storage_mount_error import (
    ExecutionStorageMountError,
)


class ExecutionStorageMountService:
    """
    Provides controlled runtime mounts for persistent execution
    volumes.

    Composes with an existing storage volume service (anything
    exposing `status(volume_id) -> str`, matching
    ExecutionStorageVolumeService), used to confirm a volume is
    AVAILABLE before it can be mounted.

    Behavior:
    - mount() admits a new mount for an AVAILABLE volume, in a
      supported mode, but only when the runtime holds no other mount
      at that path
    - unmount() permanently removes a mount
    - active() reports a runtime's currently active mounts
    - volume_mounts() reports a volume's currently active mounts,
      across every runtime it is mounted into
    - write() records a write attempt through a mount, rejecting it
      when the mount is READ_ONLY

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, volume_service):
        self._volume_service = volume_service
        self._mounts_by_id = {}
        self._lock = RLock()

    def mount(self, volume_id: str, runtime_id: str, path: str, mode: str) -> ExecutionStorageMount:
        """
        Mount volume_id into runtime_id at path, in mode.

        Raises:
            ExecutionStorageMountError: If volume_id, runtime_id, or
                path is None or blank, mode is not one of MODES,
                volume_id is unknown or not currently AVAILABLE, or
                runtime_id already holds a mount at path
        """

        self._validate_text(volume_id, "volume ID")
        self._validate_text(runtime_id, "runtime ID")
        self._validate_text(path, "path")
        self._validate_mode(mode)

        status = self._current_status(volume_id)

        if status != STATUS_AVAILABLE:
            raise ExecutionStorageMountError(
                f"Cannot mount volume ID {volume_id!r}: it is not currently available "
                f"(status {status!r})."
            )

        with self._lock:
            for existing in self._mounts_by_id.values():
                if existing.runtime_id == runtime_id and existing.path == path:
                    raise ExecutionStorageMountError(
                        f"Cannot mount at path {path!r} for runtime ID {runtime_id!r}: it already "
                        f"has a mount at that path."
                    )

            mount = ExecutionStorageMount(
                mount_id=str(uuid4()),
                volume_id=volume_id,
                runtime_id=runtime_id,
                path=path,
                mode=mode,
            )

            self._mounts_by_id[mount.mount_id] = mount

            return mount

    def unmount(self, mount_id: str) -> ExecutionStorageMount:
        """
        Permanently remove mount_id.

        Raises:
            ExecutionStorageMountError: If mount_id is None or blank,
                or no mount is registered under it
        """

        self._validate_text(mount_id, "mount ID")

        with self._lock:
            mount = self._resolve(mount_id)
            del self._mounts_by_id[mount_id]

            return mount

    def active(self, runtime_id: str) -> tuple:
        """
        The mounts currently active for runtime_id.
        """

        self._validate_text(runtime_id, "runtime ID")

        with self._lock:
            return tuple(
                mount for mount in self._mounts_by_id.values() if mount.runtime_id == runtime_id
            )

    def volume_mounts(self, volume_id: str) -> tuple:
        """
        The mounts currently active for volume_id, across every
        runtime it is mounted into.
        """

        self._validate_text(volume_id, "volume ID")

        with self._lock:
            return tuple(
                mount for mount in self._mounts_by_id.values() if mount.volume_id == volume_id
            )

    def write(self, mount_id: str) -> None:
        """
        Record a write attempt through mount_id.

        Raises:
            ExecutionStorageMountError: If mount_id is None or blank,
                no mount is registered under it, or it is READ_ONLY
        """

        self._validate_text(mount_id, "mount ID")

        with self._lock:
            mount = self._resolve(mount_id)

        if mount.mode != MODE_READ_WRITE:
            raise ExecutionStorageMountError(
                f"Cannot write through mount ID {mount_id!r}: it is {mount.mode!r}."
            )

    def _current_status(self, volume_id: str) -> str:
        try:
            return self._volume_service.status(volume_id)
        except Exception as error:
            raise ExecutionStorageMountError(
                f"Cannot resolve volume ID {volume_id!r}: it is unknown."
            ) from error

    def _resolve(self, mount_id: str) -> ExecutionStorageMount:
        mount = self._mounts_by_id.get(mount_id)

        if mount is None:
            raise ExecutionStorageMountError(f"No mount is registered under mount ID {mount_id!r}.")

        return mount

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionStorageMountError(f"Cannot use an empty or blank {field_name}.")

    @staticmethod
    def _validate_mode(mode: str) -> None:
        if mode not in MODES:
            raise ExecutionStorageMountError(f"Cannot use an unknown mode: {mode!r}.")
