from dataclasses import (
    replace,
)

from threading import (
    RLock,
)

from .execution_artifact_prefetch import (
    ExecutionArtifactPrefetch,
)

from .execution_artifact_prefetch_error import (
    ExecutionArtifactPrefetchError,
)

from .execution_artifact_retrieval_request import (
    ExecutionArtifactRetrievalRequest,
)


class ExecutionArtifactPrefetchService:
    """
    Schedules and executes prefetching of frequently consumed
    execution artifacts on behalf of consumers, ahead of when
    execution actually needs them, using an existing execution
    artifact retrieval service to fetch and an existing execution
    artifact cache service to check for and store hits.

    The service's responsibility is prefetch bookkeeping and
    orchestration only. It does not decide which artifacts are
    "frequently consumed"; a caller decides what to schedule.

    Behavior:
    - schedule() only registers a PENDING prefetch; retrieval
      permission is checked when it is executed, not when it is
      scheduled, since permissions may change in between
    - execute() requires a PENDING prefetch
    - execute() skips the actual retrieval, recording SKIPPED, when
      the cache service already has a hit for the artifact/consumer
      pair
    - execute() otherwise retrieves through the retrieval service,
      which enforces retrieval permission; a denied or otherwise
      failed attempt is recorded as FAILED rather than raising, and a
      successful attempt is recorded as SUCCEEDED and cached
    - cancel() only ever cancels a PENDING prefetch; an already
      executed or cancelled prefetch may not be cancelled again
    - pending() lists only a consumer's PENDING prefetches, in the
      order they were scheduled

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, execution_artifact_retrieval_service, execution_artifact_cache_service):
        """
        Args:
            execution_artifact_retrieval_service: The service used to
                actually retrieve an artifact, enforcing retrieval
                permission. Any object exposing `retrieve(request)`,
                raising if retrieval is denied or the artifact or
                version is unknown, is accepted
            execution_artifact_cache_service: The service used to
                check for an existing cache hit and to store a
                successful prefetch's result. Any object exposing
                `get(artifact_id, consumer)` and
                `put(artifact_id, version, consumer)` is accepted
        """

        self._execution_artifact_retrieval_service = execution_artifact_retrieval_service
        self._execution_artifact_cache_service = execution_artifact_cache_service
        self._prefetches_by_id = {}
        self._prefetch_ids_by_consumer = {}
        self._lock = RLock()

    def schedule(self, artifact_id: str, consumer: str) -> ExecutionArtifactPrefetch:
        """
        Schedule a new PENDING prefetch for an artifact on behalf of
        a consumer.

        Raises:
            ExecutionArtifactPrefetchError: If artifact_id or consumer
                is None or blank
        """

        self._validate_id(artifact_id, "artifact ID")
        self._validate_id(consumer, "consumer")

        with self._lock:
            prefetch = ExecutionArtifactPrefetch(artifact_id=artifact_id, consumer=consumer)

            self._prefetches_by_id[prefetch.prefetch_id] = prefetch
            self._prefetch_ids_by_consumer.setdefault(consumer, []).append(prefetch.prefetch_id)

            return prefetch

    def execute(self, prefetch_id: str) -> ExecutionArtifactPrefetch:
        """
        Execute a pending prefetch: skip it if the artifact is
        already cached for its consumer, otherwise attempt retrieval
        and record the outcome.

        Raises:
            ExecutionArtifactPrefetchError: If prefetch_id is None or
                blank, no prefetch is known under it, or it is not
                PENDING
        """

        self._validate_id(prefetch_id, "prefetch ID")

        with self._lock:
            prefetch = self._resolve(prefetch_id)

            if prefetch.status != "PENDING":
                raise ExecutionArtifactPrefetchError(
                    f"Cannot execute prefetch ID {prefetch_id!r}: it is {prefetch.status}, not PENDING."
                )

            updated = self._attempt(prefetch)

            self._prefetches_by_id[prefetch_id] = updated

            return updated

    def cancel(self, prefetch_id: str) -> ExecutionArtifactPrefetch:
        """
        Cancel a pending prefetch.

        Raises:
            ExecutionArtifactPrefetchError: If prefetch_id is None or
                blank, no prefetch is known under it, or it is not
                PENDING
        """

        self._validate_id(prefetch_id, "prefetch ID")

        with self._lock:
            prefetch = self._resolve(prefetch_id)

            if prefetch.status != "PENDING":
                raise ExecutionArtifactPrefetchError(
                    f"Cannot cancel prefetch ID {prefetch_id!r}: it is {prefetch.status}, not PENDING."
                )

            updated = replace(prefetch, status="CANCELLED")
            self._prefetches_by_id[prefetch_id] = updated

            return updated

    def pending(self, consumer: str) -> list:
        """
        List a consumer's still-PENDING prefetches, in the order they
        were scheduled.

        Raises:
            ExecutionArtifactPrefetchError: If consumer is None or
                blank
        """

        self._validate_id(consumer, "consumer")

        with self._lock:
            return [
                self._prefetches_by_id[prefetch_id]
                for prefetch_id in self._prefetch_ids_by_consumer.get(consumer, [])
                if self._prefetches_by_id[prefetch_id].status == "PENDING"
            ]

    def status(self, prefetch_id: str) -> ExecutionArtifactPrefetch:
        """
        Look up a prefetch's current record.

        Raises:
            ExecutionArtifactPrefetchError: If prefetch_id is None or
                blank, or no prefetch is known under it
        """

        self._validate_id(prefetch_id, "prefetch ID")

        with self._lock:
            return self._resolve(prefetch_id)

    def _attempt(self, prefetch: ExecutionArtifactPrefetch) -> ExecutionArtifactPrefetch:
        cached = self._execution_artifact_cache_service.get(prefetch.artifact_id, prefetch.consumer)

        if cached is not None:
            return replace(prefetch, status="SKIPPED")

        try:
            result = self._execution_artifact_retrieval_service.retrieve(
                ExecutionArtifactRetrievalRequest(artifact_id=prefetch.artifact_id, consumer=prefetch.consumer)
            )
        except Exception:
            return replace(prefetch, status="FAILED")

        self._execution_artifact_cache_service.put(prefetch.artifact_id, result.version, prefetch.consumer)

        return replace(prefetch, status="SUCCEEDED")

    def _resolve(self, prefetch_id: str) -> ExecutionArtifactPrefetch:
        prefetch = self._prefetches_by_id.get(prefetch_id)

        if prefetch is None:
            raise ExecutionArtifactPrefetchError(f"No prefetch is known under prefetch ID {prefetch_id!r}.")

        return prefetch

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionArtifactPrefetchError(f"Cannot use an empty or blank {field_name}.")
