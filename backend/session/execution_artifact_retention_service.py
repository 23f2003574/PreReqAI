from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from .execution_artifact_retention_error import (
    ExecutionArtifactRetentionError,
)

from .execution_artifact_retention_policy import (
    ExecutionArtifactRetentionPolicy,
)

from .execution_artifact_retention_result import (
    ExecutionArtifactRetentionResult,
)


class ExecutionArtifactRetentionService:
    """
    Evaluates configured retention policies against an artifact's
    version history, using an existing execution artifact version
    service as the source of truth for that history.

    The service's responsibility is retention bookkeeping only. It
    does not delete version records itself, since versions are
    immutable and permanent in the underlying version service;
    apply() instead tracks, for each artifact, which of its versions
    have fallen outside policy so future evaluations no longer
    consider them.

    Behavior:
    - The most recent version of an artifact is never removed,
      regardless of policy
    - A version is removed once it exceeds max_versions (by count,
      newest first) or max_age_seconds (by age), whichever a policy
      configures
    - preview() is read-only: it reports what apply() would do
      without recording anything
    - apply() records its outcome, so a later apply() or preview()
      call no longer reports an already-removed version

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, execution_artifact_version_service):
        """
        Args:
            execution_artifact_version_service: The service used as
                the source of truth for an artifact's version
                history. Any object exposing `history(artifact_id)`
                and `latest(artifact_id)` is accepted
        """

        self._execution_artifact_version_service = execution_artifact_version_service
        self._policies_by_artifact = {}
        self._removed_versions_by_artifact = {}
        self._lock = RLock()

    def configure(self, artifact_id: str, policy: ExecutionArtifactRetentionPolicy) -> ExecutionArtifactRetentionPolicy:
        """
        Set the retention policy an artifact's version history should
        be evaluated against, replacing any policy configured before.

        Raises:
            ExecutionArtifactRetentionError: If artifact_id is None
                or blank, or policy is not an
                ExecutionArtifactRetentionPolicy
        """

        self._validate_id(artifact_id, "artifact ID")

        if not isinstance(policy, ExecutionArtifactRetentionPolicy):
            raise ExecutionArtifactRetentionError(
                "Cannot configure an invalid policy: policy must be an ExecutionArtifactRetentionPolicy."
            )

        with self._lock:
            self._policies_by_artifact[artifact_id] = policy

            return policy

    def policy(self, artifact_id: str) -> ExecutionArtifactRetentionPolicy:
        """
        Look up an artifact's currently configured retention policy.

        Raises:
            ExecutionArtifactRetentionError: If artifact_id is None
                or blank, or no policy is configured for it
        """

        self._validate_id(artifact_id, "artifact ID")

        with self._lock:
            return self._resolve_policy(artifact_id)

    def preview(self, artifact_id: str) -> ExecutionArtifactRetentionResult:
        """
        Report what apply() would remove and retain right now,
        without recording anything.

        Raises:
            ExecutionArtifactRetentionError: If artifact_id is None
                or blank, or no policy is configured for it
        """

        self._validate_id(artifact_id, "artifact ID")

        with self._lock:
            return self._evaluate(artifact_id)

    def apply(self, artifact_id: str) -> ExecutionArtifactRetentionResult:
        """
        Evaluate an artifact's version history against its configured
        policy and record which versions fall outside it, so later
        calls no longer report them as newly removed.

        Raises:
            ExecutionArtifactRetentionError: If artifact_id is None
                or blank, or no policy is configured for it
        """

        self._validate_id(artifact_id, "artifact ID")

        with self._lock:
            result = self._evaluate(artifact_id)

            already_removed = self._removed_versions_by_artifact.setdefault(artifact_id, set())
            already_removed.update(version.version for version in result.removed)

            return result

    def _evaluate(self, artifact_id: str) -> ExecutionArtifactRetentionResult:
        policy = self._resolve_policy(artifact_id)

        history = list(self._execution_artifact_version_service.history(artifact_id))
        already_removed = self._removed_versions_by_artifact.get(artifact_id, set())

        history = [version for version in history if version.version not in already_removed]

        if not history:
            return ExecutionArtifactRetentionResult(removed=(), retained=())

        latest_version_number = self._execution_artifact_version_service.latest(artifact_id).version

        kept_by_count = None

        if policy.max_versions is not None:
            newest_first = sorted(history, key=lambda version: version.version, reverse=True)
            kept_by_count = {version.version for version in newest_first[: policy.max_versions]}

        now = datetime.now(timezone.utc)

        removed = []
        retained = []

        for version in history:
            if version.version == latest_version_number:
                retained.append(version)
                continue

            expired_by_age = (
                policy.max_age_seconds is not None
                and (now - version.created_at).total_seconds() > policy.max_age_seconds
            )

            exceeds_count = kept_by_count is not None and version.version not in kept_by_count

            if expired_by_age or exceeds_count:
                removed.append(version)
            else:
                retained.append(version)

        return ExecutionArtifactRetentionResult(removed=tuple(removed), retained=tuple(retained))

    def _resolve_policy(self, artifact_id: str) -> ExecutionArtifactRetentionPolicy:
        policy = self._policies_by_artifact.get(artifact_id)

        if policy is None:
            raise ExecutionArtifactRetentionError(
                f"No retention policy is configured for artifact ID {artifact_id!r}."
            )

        return policy

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionArtifactRetentionError(f"Cannot use an empty or blank {field_name}.")
