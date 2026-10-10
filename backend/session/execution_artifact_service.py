from threading import (
    RLock,
)

from .execution_artifact import (
    ExecutionArtifact,
)

from .execution_artifact_error import (
    ExecutionArtifactError,
)


class ExecutionArtifactService:
    """
    Registers artifacts produced during execution sessions, keyed by
    a unique artifact ID and grouped by the session that produced
    them.

    The service's responsibility is registry bookkeeping only. It
    does not create artifacts or manage where they are stored; it
    relies on the existing execution session service, given at
    construction time, only to confirm a session ID is genuinely
    known before an artifact is registered on its behalf.

    Behavior:
    - A session may have any number of registered artifacts
    - list() returns a session's artifacts in registration order
    - Artifact IDs are unique across all sessions
    - remove() only ever deletes the artifact: a session that has had
      every artifact removed still has an (empty) list() and still
      accepts new registrations

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, execution_session_service):
        """
        Args:
            execution_session_service: The service used to confirm a
                session ID is known before an artifact is registered
                on its behalf. Any object exposing
                `session(session_id)`, raising if the session is
                unknown, is accepted
        """

        self._execution_session_service = execution_session_service
        self._artifacts = {}
        self._artifact_ids_by_session = {}
        self._lock = RLock()

    def register(self, session_id: str, artifact: ExecutionArtifact) -> ExecutionArtifact:
        """
        Register an artifact on behalf of a session.

        Raises:
            ExecutionArtifactError: If session_id is None or blank,
                artifact is not an ExecutionArtifact belonging to
                session_id, the execution session service does not
                recognize session_id, or the artifact ID is already
                registered
        """

        self._validate_id(session_id, "session ID")

        if not isinstance(artifact, ExecutionArtifact):
            raise ExecutionArtifactError(
                "Cannot register an invalid artifact: artifact must be an ExecutionArtifact."
            )

        if artifact.session_id != session_id:
            raise ExecutionArtifactError(
                f"Cannot register an artifact for session ID {artifact.session_id!r} on behalf of "
                f"session ID {session_id!r}."
            )

        with self._lock:
            self._ensure_session_known(session_id)

            if artifact.artifact_id in self._artifacts:
                raise ExecutionArtifactError(
                    f"Artifact ID {artifact.artifact_id!r} is already registered."
                )

            self._artifacts[artifact.artifact_id] = artifact
            self._artifact_ids_by_session.setdefault(session_id, []).append(artifact.artifact_id)

            return artifact

    def get(self, artifact_id: str) -> ExecutionArtifact:
        """
        Look up a single registered artifact.

        Raises:
            ExecutionArtifactError: If artifact_id is None or blank,
                or no artifact is registered under it
        """

        self._validate_id(artifact_id, "artifact ID")

        with self._lock:
            return self._resolve(artifact_id)

    def list(self, session_id: str) -> list:
        """
        List a session's registered artifacts in the order they were
        registered.

        Raises:
            ExecutionArtifactError: If session_id is None or blank,
                or the execution session service does not recognize
                session_id
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            self._ensure_session_known(session_id)

            return [
                self._artifacts[artifact_id]
                for artifact_id in self._artifact_ids_by_session.get(session_id, [])
            ]

    def remove(self, artifact_id: str) -> ExecutionArtifact:
        """
        Remove a registered artifact. The session that produced it is
        left untouched, including when this was its last artifact.

        Raises:
            ExecutionArtifactError: If artifact_id is None or blank,
                or no artifact is registered under it
        """

        self._validate_id(artifact_id, "artifact ID")

        with self._lock:
            artifact = self._resolve(artifact_id)

            del self._artifacts[artifact_id]
            self._artifact_ids_by_session[artifact.session_id].remove(artifact_id)

            return artifact

    def _resolve(self, artifact_id: str) -> ExecutionArtifact:
        artifact = self._artifacts.get(artifact_id)

        if artifact is None:
            raise ExecutionArtifactError(f"No artifact is known under artifact ID {artifact_id!r}.")

        return artifact

    def _ensure_session_known(self, session_id: str) -> None:
        try:
            self._execution_session_service.session(session_id)
        except Exception as error:
            raise ExecutionArtifactError(f"No session is known under session ID {session_id!r}.") from error

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionArtifactError(f"Cannot use an empty or blank {field_name}.")
