from threading import (
    RLock,
)

from .execution_artifact_discovery_error import (
    ExecutionArtifactDiscoveryError,
)

from .execution_artifact_query import (
    ExecutionArtifactQuery,
)

from .execution_artifact_search_result import (
    ExecutionArtifactSearchResult,
)


class ExecutionArtifactDiscoveryService:
    """
    Lets consumers discover execution artifacts already known to an
    execution artifact registry, by session, type, tag, exact
    metadata, or any combination of these.

    The service's responsibility is discovery only. It never creates,
    stores, or mutates artifacts, metadata, or tags; it relies on an
    existing execution artifact registry and execution artifact
    metadata service, both given at construction time, as the sole
    sources of truth for artifact, tag, and metadata data, and on its
    own lightweight index, built by index(), to know which artifact
    IDs are eligible for a type-only, metadata-only, or otherwise
    unscoped search.

    Behavior:
    - index() must be called for an artifact before it can be found
      by a query that gives neither session_id nor tag; by_session()
      and by_tag() never require indexing, since the registry and
      metadata service already expose those lookups directly and are
      used as the candidate source in that case
    - A query matches an artifact only when every criterion given on
      it matches exactly: session ID, type, tag membership, and every
      metadata key/value pair
    - Results are deterministic: candidates are considered in the
      order their source naturally produces them (registration order
      for a session, tag-application order for a tag, indexing order
      otherwise), and that order is preserved in the returned list
    - Unknown sessions and unknown tags produce empty results rather
      than errors
    - Never mutates artifacts, metadata, or tags

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, execution_artifact_service, execution_artifact_metadata_service):
        """
        Args:
            execution_artifact_service: The registry used to resolve
                artifact records. Any object exposing
                `get(artifact_id)` and `list(session_id)` is accepted
            execution_artifact_metadata_service: The service used to
                resolve tags and metadata. Any object exposing
                `tags(artifact_id)`, `get(artifact_id, key)`, and
                `find(tag)` is accepted
        """

        self._execution_artifact_service = execution_artifact_service
        self._execution_artifact_metadata_service = execution_artifact_metadata_service
        self._indexed_artifact_ids = []
        self._indexed_artifact_id_set = set()
        self._lock = RLock()

    def index(self, artifact_id: str) -> None:
        """
        Make an artifact eligible for a type-only, metadata-only, or
        otherwise unscoped search. A no-op if already indexed.

        Raises:
            ExecutionArtifactDiscoveryError: If artifact_id is None or
                blank, or the execution artifact registry does not
                recognize it
        """

        self._validate_id(artifact_id, "artifact ID")

        with self._lock:
            self._ensure_artifact_known(artifact_id)

            if artifact_id not in self._indexed_artifact_id_set:
                self._indexed_artifact_id_set.add(artifact_id)
                self._indexed_artifact_ids.append(artifact_id)

    def search(self, query: ExecutionArtifactQuery) -> list:
        """
        Search for artifacts matching every criterion given on a
        query.

        Raises:
            ExecutionArtifactDiscoveryError: If query is not an
                ExecutionArtifactQuery
        """

        if not isinstance(query, ExecutionArtifactQuery):
            raise ExecutionArtifactDiscoveryError(
                "Cannot search with an invalid query: query must be an ExecutionArtifactQuery."
            )

        with self._lock:
            results = []

            for artifact_id in self._candidates(query):
                score = self._score(artifact_id, query)

                if score is not None:
                    results.append(ExecutionArtifactSearchResult(artifact_id=artifact_id, score=score))

            return results

    def by_session(self, session_id: str) -> list:
        """
        Find every artifact registered under a session, in
        registration order. Returns an empty list for an unknown
        session.
        """

        return self.search(ExecutionArtifactQuery(session_id=session_id))

    def by_type(self, type: str) -> list:
        """
        Find every indexed artifact of a given type.
        """

        return self.search(ExecutionArtifactQuery(type=type))

    def by_tag(self, tag: str) -> list:
        """
        Find every artifact currently tagged with a given tag, in the
        order they were tagged. Returns an empty list for an unknown
        tag.
        """

        return self.search(ExecutionArtifactQuery(tag=tag))

    def _candidates(self, query: ExecutionArtifactQuery) -> list:
        if query.session_id is not None:
            try:
                artifacts = self._execution_artifact_service.list(query.session_id)
            except Exception:
                return []

            return [artifact.artifact_id for artifact in artifacts]

        if query.tag is not None:
            try:
                tags = self._execution_artifact_metadata_service.find(query.tag)
            except Exception:
                return []

            return [tag_entry.artifact_id for tag_entry in tags]

        return list(self._indexed_artifact_ids)

    def _score(self, artifact_id: str, query: ExecutionArtifactQuery):
        try:
            artifact = self._execution_artifact_service.get(artifact_id)
        except Exception:
            return None

        matched = 0

        if query.session_id is not None:
            if artifact.session_id != query.session_id:
                return None

            matched += 1

        if query.type is not None:
            if artifact.type != query.type:
                return None

            matched += 1

        if query.tag is not None:
            if not self._has_tag(artifact_id, query.tag):
                return None

            matched += 1

        for key, value in query.metadata.items():
            if not self._has_metadata(artifact_id, key, value):
                return None

            matched += 1

        return float(matched)

    def _has_tag(self, artifact_id: str, tag: str) -> bool:
        try:
            tags = self._execution_artifact_metadata_service.tags(artifact_id)
        except Exception:
            return False

        return any(entry.tag == tag for entry in tags)

    def _has_metadata(self, artifact_id: str, key: str, value) -> bool:
        try:
            entry = self._execution_artifact_metadata_service.get(artifact_id, key)
        except Exception:
            return False

        return entry.value == value

    def _ensure_artifact_known(self, artifact_id: str) -> None:
        try:
            self._execution_artifact_service.get(artifact_id)
        except Exception as error:
            raise ExecutionArtifactDiscoveryError(
                f"No artifact is known under artifact ID {artifact_id!r}."
            ) from error

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ExecutionArtifactDiscoveryError(f"Cannot use an empty or blank {field_name}.")
