from dataclasses import (
    replace,
)

from threading import (
    RLock,
)

from .execution_artifact_consumption_error import (
    ExecutionArtifactConsumptionError,
)

from .execution_artifact_consumption_session import (
    ExecutionArtifactConsumptionSession,
)

from .execution_artifact_retrieval_request import (
    ExecutionArtifactRetrievalRequest,
)


class ExecutionArtifactConsumptionService:
    """
    Tracks which execution artifacts a consumer is actively
    consuming, grouped into consumption sessions, using an existing
    execution artifact retrieval service to confirm the consumer has
    retrieval access to an artifact before it enters a session.

    The service's responsibility is session bookkeeping only. It
    does not retrieve or mutate artifacts themselves.

    Behavior:
    - start(), add(), and remove() each require the consumer to
      already have retrieval access to the artifact involved
    - An artifact may appear at most once in a session's artifact_ids;
      adding one already present is rejected, whether given to
      start() or add()
    - A FINISHED session is immutable: add(), remove(), and finish()
      all reject a session that has already finished
    - active() lists only a consumer's still-ACTIVE sessions, tracked
      independently of finished ones

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, execution_artifact_retrieval_service):
        """
        Args:
            execution_artifact_retrieval_service: The service used to
                confirm a consumer has retrieval access to an
                artifact before it enters a session. Any object
                exposing `retrieve(request)`, raising if retrieval is
                denied or the artifact or version is unknown, is
                accepted
        """

        self._execution_artifact_retrieval_service = execution_artifact_retrieval_service
        self._sessions_by_id = {}
        self._active_ids_by_consumer = {}
        self._lock = RLock()

    def start(self, consumer: str, artifact_ids) -> ExecutionArtifactConsumptionSession:
        """
        Start a new ACTIVE consumption session for a consumer,
        tracking a starting set of artifacts.

        Raises:
            ExecutionArtifactConsumptionError: If consumer is None or
                blank, artifact_ids contains a duplicate, or the
                consumer lacks retrieval access to any of the given
                artifacts
        """

        self._validate_id(consumer, "consumer")

        if artifact_ids is None:
            raise ExecutionArtifactConsumptionError("Cannot start a consumption session with a None artifact_ids.")

        artifact_id_list = list(artifact_ids)

        with self._lock:
            for artifact_id in artifact_id_list:
                self._ensure_authorized(artifact_id, consumer)

            session = ExecutionArtifactConsumptionSession(consumer=consumer, artifact_ids=tuple(artifact_id_list))

            self._sessions_by_id[session.consumption_id] = session
            self._active_ids_by_consumer.setdefault(consumer, []).append(session.consumption_id)

            return session

    def add(self, consumption_id: str, artifact_id: str) -> ExecutionArtifactConsumptionSession:
        """
        Add an artifact to an ACTIVE session.

        Raises:
            ExecutionArtifactConsumptionError: If consumption_id or
                artifact_id is None or blank, no session is known
                under consumption_id, it has already finished, the
                artifact is already tracked by it, or the consumer
                lacks retrieval access to the artifact
        """

        self._validate_id(consumption_id, "consumption ID")
        self._validate_id(artifact_id, "artifact ID")

        with self._lock:
            session = self._resolve(consumption_id)

            self._ensure_active(session)

            if artifact_id in session.artifact_ids:
                raise ExecutionArtifactConsumptionError(
                    f"Artifact ID {artifact_id!r} is already tracked by consumption ID {consumption_id!r}."
                )

            self._ensure_authorized(artifact_id, session.consumer)

            updated = replace(session, artifact_ids=session.artifact_ids + (artifact_id,))
            self._sessions_by_id[consumption_id] = updated

            return updated

    def remove(self, consumption_id: str, artifact_id: str) -> ExecutionArtifactConsumptionSession:
        """
        Remove an artifact from an ACTIVE session.

        Raises:
            ExecutionArtifactConsumptionError: If consumption_id or
                artifact_id is None or blank, no session is known
                under consumption_id, it has already finished, or the
                artifact is not currently tracked by it
        """

        self._validate_id(consumption_id, "consumption ID")
        self._validate_id(artifact_id, "artifact ID")

        with self._lock:
            session = self._resolve(consumption_id)

            self._ensure_active(session)

            if artifact_id not in session.artifact_ids:
                raise ExecutionArtifactConsumptionError(
                    f"Artifact ID {artifact_id!r} is not tracked by consumption ID {consumption_id!r}."
                )

            updated = replace(
                session,
                artifact_ids=tuple(tracked for tracked in session.artifact_ids if tracked != artifact_id),
            )
            self._sessions_by_id[consumption_id] = updated

            return updated

    def finish(self, consumption_id: str) -> ExecutionArtifactConsumptionSession:
        """
        Finish an ACTIVE session, making it immutable.

        Raises:
            ExecutionArtifactConsumptionError: If consumption_id is
                None or blank, no session is known under it, or it
                has already finished
        """

        self._validate_id(consumption_id, "consumption ID")

        with self._lock:
            session = self._resolve(consumption_id)

            self._ensure_active(session)

            updated = replace(session, status="FINISHED")
            self._sessions_by_id[consumption_id] = updated
            self._active_ids_by_consumer[session.consumer].remove(consumption_id)

            return updated

    def active(self, consumer: str) -> list:
        """
        List a consumer's still-ACTIVE sessions, in the order they
        were started.

        Raises:
            ExecutionArtifactConsumptionError: If consumer is None or
                blank
        """

        self._validate_id(consumer, "consumer")

        with self._lock:
            return [
                self._sessions_by_id[consumption_id]
                for consumption_id in self._active_ids_by_consumer.get(consumer, [])
            ]

    def _ensure_active(self, session: ExecutionArtifactConsumptionSession) -> None:
        if session.status != "ACTIVE":
            raise ExecutionArtifactConsumptionError(
                f"Cannot modify consumption ID {session.consumption_id!r}: it is {session.status}, not "
                "ACTIVE."
            )

    def _ensure_authorized(self, artifact_id: str, consumer: str) -> None:
        self._validate_id(artifact_id, "artifact ID")

        try:
            self._execution_artifact_retrieval_service.retrieve(
                ExecutionArtifactRetrievalRequest(artifact_id=artifact_id, consumer=consumer)
            )
        except Exception as error:
            raise ExecutionArtifactConsumptionError(
                f"Consumer {consumer!r} is not permitted to consume artifact ID {artifact_id!r}."
            ) from error

    def _resolve(self, consumption_id: str) -> ExecutionArtifactConsumptionSession:
        session = self._sessions_by_id.get(consumption_id)

        if session is None:
            raise ExecutionArtifactConsumptionError(
                f"No consumption session is known under consumption ID {consumption_id!r}."
            )

        return session

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionArtifactConsumptionError(f"Cannot use an empty or blank {field_name}.")
