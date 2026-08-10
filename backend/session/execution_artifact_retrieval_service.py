from threading import (
    RLock,
)

from .execution_artifact_retrieval_error import (
    ExecutionArtifactRetrievalError,
)

from .execution_artifact_retrieval_request import (
    ExecutionArtifactRetrievalRequest,
)

from .execution_artifact_retrieval_result import (
    ExecutionArtifactRetrievalResult,
)


class ExecutionArtifactRetrievalService:
    """
    Lets consumers retrieve execution artifacts already known to an
    execution artifact registry, resolving which version to hand
    back and validating the requesting consumer's access before
    doing so.

    The service's responsibility is retrieval only. It never creates,
    stores, or mutates artifacts, versions, or permissions; it relies
    on an existing execution artifact registry, version service, and
    access service, all given at construction time, as the sole
    sources of truth.

    Behavior:
    - retrieve() defaults to an artifact's latest version when a
      request gives none
    - retrieve() rejects a request from a consumer without READ
      access to the artifact
    - retrieve() rejects a request for a version that does not exist
    - latest() and version() are unauthenticated convenience lookups:
      they resolve a version's location directly, without a consumer
      to check access against
    - Never mutates artifacts, versions, or permissions

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(
        self,
        execution_artifact_service,
        execution_artifact_version_service,
        execution_artifact_access_service,
    ):
        """
        Args:
            execution_artifact_service: The registry used to confirm
                an artifact ID is known before it is retrieved. Any
                object exposing `get(artifact_id)`, raising if the
                artifact is unknown, is accepted
            execution_artifact_version_service: The service used to
                resolve a specific or latest version. Any object
                exposing `get(artifact_id, version)` and
                `latest(artifact_id)` is accepted
            execution_artifact_access_service: The service used to
                check a consumer's access. Any object exposing
                `authorize(artifact_id, principal, operation)`,
                returning an object with an `.allowed` attribute, is
                accepted
        """

        self._execution_artifact_service = execution_artifact_service
        self._execution_artifact_version_service = execution_artifact_version_service
        self._execution_artifact_access_service = execution_artifact_access_service
        self._lock = RLock()

    def retrieve(self, request: ExecutionArtifactRetrievalRequest) -> ExecutionArtifactRetrievalResult:
        """
        Retrieve an artifact on behalf of a consumer, resolving its
        latest version when the request does not specify one.

        Raises:
            ExecutionArtifactRetrievalError: If request is not an
                ExecutionArtifactRetrievalRequest, the execution
                artifact registry does not recognize its artifact ID,
                the requesting consumer is not granted READ access to
                the artifact, or the requested version does not exist
        """

        if not isinstance(request, ExecutionArtifactRetrievalRequest):
            raise ExecutionArtifactRetrievalError(
                "Cannot retrieve with an invalid request: request must be an "
                "ExecutionArtifactRetrievalRequest."
            )

        with self._lock:
            self._ensure_artifact_known(request.artifact_id)
            self._ensure_authorized(request.artifact_id, request.consumer)

            version_entry = self._resolve_version(request.artifact_id, request.version)

            return self._to_result(version_entry)

    def latest(self, artifact_id: str) -> ExecutionArtifactRetrievalResult:
        """
        Resolve an artifact's latest version directly, without an
        access check.

        Raises:
            ExecutionArtifactRetrievalError: If artifact_id is None or
                blank, the execution artifact registry does not
                recognize it, or the artifact has no versions yet
        """

        self._validate_id(artifact_id, "artifact ID")

        with self._lock:
            self._ensure_artifact_known(artifact_id)

            return self._to_result(self._resolve_version(artifact_id, None))

    def version(self, artifact_id: str, version: int) -> ExecutionArtifactRetrievalResult:
        """
        Resolve a specific version of an artifact directly, without
        an access check.

        Raises:
            ExecutionArtifactRetrievalError: If artifact_id is None or
                blank, the execution artifact registry does not
                recognize it, or the requested version does not exist
        """

        self._validate_id(artifact_id, "artifact ID")

        with self._lock:
            self._ensure_artifact_known(artifact_id)

            return self._to_result(self._resolve_version(artifact_id, version))

    def _resolve_version(self, artifact_id: str, version: int | None):
        try:
            if version is None:
                return self._execution_artifact_version_service.latest(artifact_id)

            return self._execution_artifact_version_service.get(artifact_id, version)
        except Exception as error:
            if version is None:
                raise ExecutionArtifactRetrievalError(
                    f"Artifact ID {artifact_id!r} has no versions available to retrieve."
                ) from error

            raise ExecutionArtifactRetrievalError(
                f"Version {version!r} is not available for artifact ID {artifact_id!r}."
            ) from error

    def _ensure_authorized(self, artifact_id: str, consumer: str) -> None:
        result = self._execution_artifact_access_service.authorize(artifact_id, consumer, "READ")

        if not result.allowed:
            raise ExecutionArtifactRetrievalError(
                f"Consumer {consumer!r} is not authorized to read artifact ID {artifact_id!r}."
            )

    def _ensure_artifact_known(self, artifact_id: str) -> None:
        try:
            self._execution_artifact_service.get(artifact_id)
        except Exception as error:
            raise ExecutionArtifactRetrievalError(
                f"No artifact is known under artifact ID {artifact_id!r}."
            ) from error

    @staticmethod
    def _to_result(version_entry) -> ExecutionArtifactRetrievalResult:
        return ExecutionArtifactRetrievalResult(
            artifact_id=version_entry.artifact_id,
            version=version_entry.version,
            location=version_entry.location,
        )

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionArtifactRetrievalError(f"Cannot use an empty or blank {field_name}.")
