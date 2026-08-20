from dataclasses import (
    replace,
)

from threading import (
    RLock,
)

from uuid import uuid4

from .workspace_execution_artifact import (
    ARTIFACT_TYPES,
    STATUS_ACTIVE,
    STATUS_REMOVED,
    WorkspaceExecutionArtifact,
)

from .workspace_execution_artifact_error import (
    WorkspaceExecutionArtifactError,
)


class ExecutionArtifactRegistryService:
    """
    Registers outputs produced by execution runtimes as first-class,
    addressable artifacts.

    Composes with an existing runtime lifecycle collaborator (anything
    exposing `state(runtime_id) -> object with .state`, matching
    ExecutionRuntimeStateService), used to reject registration for
    runtimes that are not known.

    Behavior:
    - register() admits a new ACTIVE artifact for a known runtime,
      rejecting a name already active for that runtime
    - get() returns an artifact by ID, but not one that has been
      removed
    - list() reports the active artifacts registered for a runtime
    - remove() marks an artifact REMOVED, after which it can no longer
      be retrieved as active

    Artifact names are scoped per runtime: the same name may be active
    on two different runtimes at once, but not twice on the same
    runtime.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, runtime_state_service):
        self._runtime_state_service = runtime_state_service
        self._artifacts_by_id = {}
        self._lock = RLock()

    def register(
        self,
        runtime_id: str,
        name: str,
        artifact_type: str,
        location: str,
    ) -> WorkspaceExecutionArtifact:
        """
        Register a new ACTIVE artifact produced by runtime_id.

        Raises:
            WorkspaceExecutionArtifactError: If runtime_id, name, or
                location is None or blank, artifact_type is not one of
                ARTIFACT_TYPES, runtime_id is unknown, or name is
                already active on runtime_id
        """

        self._validate_text(runtime_id, "runtime ID")
        self._validate_text(name, "name")
        self._validate_text(location, "location")

        if artifact_type not in ARTIFACT_TYPES:
            raise WorkspaceExecutionArtifactError(
                f"Cannot register an artifact with an unknown artifact type: {artifact_type!r}."
            )

        with self._lock:
            self._require_known_runtime(runtime_id)

            if any(
                artifact.runtime_id == runtime_id
                and artifact.name == name
                and artifact.status == STATUS_ACTIVE
                for artifact in self._artifacts_by_id.values()
            ):
                raise WorkspaceExecutionArtifactError(
                    f"Cannot register artifact name {name!r}: it is already active on runtime "
                    f"ID {runtime_id!r}."
                )

            artifact = WorkspaceExecutionArtifact(
                artifact_id=str(uuid4()),
                runtime_id=runtime_id,
                name=name,
                artifact_type=artifact_type,
                location=location,
                status=STATUS_ACTIVE,
            )

            self._artifacts_by_id[artifact.artifact_id] = artifact

            return artifact

    def get(self, artifact_id: str) -> WorkspaceExecutionArtifact:
        """
        Return the active artifact registered under artifact_id.

        Raises:
            WorkspaceExecutionArtifactError: If artifact_id is None or
                blank, no artifact is registered under it, or it has
                been removed
        """

        self._validate_text(artifact_id, "artifact ID")

        with self._lock:
            return self._resolve_active(artifact_id)

    def list(self, runtime_id: str) -> tuple:
        """
        The active artifacts currently registered for runtime_id.

        Raises:
            WorkspaceExecutionArtifactError: If runtime_id is None or
                blank
        """

        self._validate_text(runtime_id, "runtime ID")

        with self._lock:
            return tuple(
                artifact
                for artifact in self._artifacts_by_id.values()
                if artifact.runtime_id == runtime_id and artifact.status == STATUS_ACTIVE
            )

    def remove(self, artifact_id: str) -> WorkspaceExecutionArtifact:
        """
        Mark the artifact registered under artifact_id REMOVED.

        Raises:
            WorkspaceExecutionArtifactError: If artifact_id is None or
                blank, no artifact is registered under it, or it has
                already been removed
        """

        self._validate_text(artifact_id, "artifact ID")

        with self._lock:
            artifact = self._resolve_active(artifact_id)

            removed = replace(artifact, status=STATUS_REMOVED)
            self._artifacts_by_id[artifact_id] = removed

            return removed

    def _require_known_runtime(self, runtime_id: str) -> None:
        try:
            self._runtime_state_service.state(runtime_id)
        except Exception as error:
            raise WorkspaceExecutionArtifactError(
                f"Cannot resolve runtime ID {runtime_id!r}: it is unknown."
            ) from error

    def _resolve_active(self, artifact_id: str) -> WorkspaceExecutionArtifact:
        artifact = self._artifacts_by_id.get(artifact_id)

        if artifact is None or artifact.status != STATUS_ACTIVE:
            raise WorkspaceExecutionArtifactError(
                f"No active artifact is registered under artifact ID {artifact_id!r}."
            )

        return artifact

    @staticmethod
    def _validate_text(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise WorkspaceExecutionArtifactError(f"Cannot use an empty or blank {field_name}.")
