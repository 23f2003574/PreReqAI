from dataclasses import (
    replace,
)

from threading import (
    RLock,
)

from uuid import uuid4

from .execution_runtime_state import (
    TERMINAL_STATES,
)

from .execution_storage_volume import (
    ExecutionStorageVolume,
    STATUS_ATTACHED,
    STATUS_AVAILABLE,
)

from .execution_storage_volume_error import (
    ExecutionStorageVolumeError,
)


class ExecutionStorageVolumeService:
    """
    Provides persistent storage volumes that execution runtimes can
    attach and use.

    Composes with an existing runtime state service (anything
    exposing `state(runtime_id) -> object with .state`, matching
    ExecutionRuntimeStateService), used to reject attachment for
    runtimes that have already reached a terminal state (STOPPED,
    FAILED).

    Behavior:
    - create() admits a new AVAILABLE volume with a positive size
    - attach() moves a volume to ATTACHED for a non-terminal runtime,
      but only when the volume holds no other active attachment
    - detach() releases a volume back to AVAILABLE, but only when it
      is currently attached to the given runtime
    - delete() permanently removes a volume, but never one that is
      currently attached
    - status() reports a volume's current status
    - active() reports the volumes currently attached to a runtime

    Each volume permits at most one active attachment at a time.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, state_service):
        self._state_service = state_service
        self._volumes_by_id = {}
        self._attachment_by_volume = {}
        self._lock = RLock()

    def create(self, scope_id: str, size: float) -> ExecutionStorageVolume:
        """
        Create a new AVAILABLE volume for scope_id.

        Raises:
            ExecutionStorageVolumeError: If scope_id is None or
                blank, or size is not a positive number
        """

        self._validate_text(scope_id, "scope ID")

        volume = ExecutionStorageVolume(
            volume_id=str(uuid4()),
            scope_id=scope_id,
            size=size,
            status=STATUS_AVAILABLE,
        )

        with self._lock:
            self._volumes_by_id[volume.volume_id] = volume

        return volume

    def attach(self, volume_id: str, runtime_id: str) -> ExecutionStorageVolume:
        """
        Attach volume_id to runtime_id, moving it to ATTACHED.

        Raises:
            ExecutionStorageVolumeError: If volume_id or runtime_id is
                None or blank, no volume is registered under
                volume_id, runtime_id is unknown or has reached a
                terminal state, or the volume already has an active
                attachment
        """

        self._validate_text(volume_id, "volume ID")
        self._validate_text(runtime_id, "runtime ID")

        with self._lock:
            volume = self._resolve(volume_id)

            current_state = self._current_state(runtime_id)

            if current_state in TERMINAL_STATES:
                raise ExecutionStorageVolumeError(
                    f"Cannot attach volume ID {volume_id!r} to runtime ID {runtime_id!r}: it has "
                    f"reached a terminal state ({current_state!r})."
                )

            if volume.status == STATUS_ATTACHED:
                raise ExecutionStorageVolumeError(
                    f"Cannot attach volume ID {volume_id!r}: it already has an active attachment."
                )

            attached = replace(volume, status=STATUS_ATTACHED)
            self._volumes_by_id[volume_id] = attached
            self._attachment_by_volume[volume_id] = runtime_id

            return attached

    def detach(self, volume_id: str, runtime_id: str) -> ExecutionStorageVolume:
        """
        Detach volume_id from runtime_id, releasing it back to
        AVAILABLE.

        Raises:
            ExecutionStorageVolumeError: If volume_id or runtime_id is
                None or blank, no volume is registered under
                volume_id, or it is not currently attached to
                runtime_id
        """

        self._validate_text(volume_id, "volume ID")
        self._validate_text(runtime_id, "runtime ID")

        with self._lock:
            volume = self._resolve(volume_id)

            if self._attachment_by_volume.get(volume_id) != runtime_id:
                raise ExecutionStorageVolumeError(
                    f"Cannot detach volume ID {volume_id!r} from runtime ID {runtime_id!r}: it is "
                    f"not currently attached to that runtime."
                )

            del self._attachment_by_volume[volume_id]

            detached = replace(volume, status=STATUS_AVAILABLE)
            self._volumes_by_id[volume_id] = detached

            return detached

    def delete(self, volume_id: str) -> None:
        """
        Permanently remove volume_id.

        Raises:
            ExecutionStorageVolumeError: If volume_id is None or
                blank, no volume is registered under it, or it is
                currently attached
        """

        self._validate_text(volume_id, "volume ID")

        with self._lock:
            volume = self._resolve(volume_id)

            if volume.status == STATUS_ATTACHED:
                raise ExecutionStorageVolumeError(
                    f"Cannot delete volume ID {volume_id!r}: it is currently attached."
                )

            del self._volumes_by_id[volume_id]

    def status(self, volume_id: str) -> str:
        """
        The current status of volume_id.

        Raises:
            ExecutionStorageVolumeError: If volume_id is None or
                blank, or no volume is registered under it
        """

        self._validate_text(volume_id, "volume ID")

        with self._lock:
            return self._resolve(volume_id).status

    def active(self, runtime_id: str) -> tuple:
        """
        The volumes currently attached to runtime_id.
        """

        self._validate_text(runtime_id, "runtime ID")

        with self._lock:
            return tuple(
                volume
                for volume_id, volume in self._volumes_by_id.items()
                if self._attachment_by_volume.get(volume_id) == runtime_id
            )

    def _current_state(self, runtime_id: str) -> str:
        try:
            return self._state_service.state(runtime_id).state
        except Exception as error:
            raise ExecutionStorageVolumeError(
                f"Cannot resolve runtime ID {runtime_id!r}: it is unknown."
            ) from error

    def _resolve(self, volume_id: str) -> ExecutionStorageVolume:
        volume = self._volumes_by_id.get(volume_id)

        if volume is None:
            raise ExecutionStorageVolumeError(f"No volume is registered under volume ID {volume_id!r}.")

        return volume

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionStorageVolumeError(f"Cannot use an empty or blank {field_name}.")
