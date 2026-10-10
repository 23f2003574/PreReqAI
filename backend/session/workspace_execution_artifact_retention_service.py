from dataclasses import (
    replace,
)

from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from .workspace_execution_artifact_promotion import (
    STAGE_PRODUCTION,
    STATUS_ACTIVE as PROMOTION_STATUS_ACTIVE,
)

from .workspace_execution_artifact_retention_error import (
    WorkspaceExecutionArtifactRetentionError,
)

from .workspace_execution_artifact_retention_policy import (
    WorkspaceExecutionArtifactRetentionPolicy,
)


class WorkspaceExecutionArtifactRetentionService:
    """
    Controls how long execution artifact versions remain eligible for
    storage and retrieval, using an existing artifact registry, a
    version resolver, and a promotion service as the sources of truth
    for artifact existence, version age, and production status.

    The service's responsibility is retention bookkeeping only. It
    does not delete versions or artifact contents itself; eligible()
    reports whether a version has aged out of its policy so a
    separate garbage collection process may act on it.

    Behavior:
    - configure() replaces an artifact's policy with a fresh, enabled
      one
    - A version currently ACTIVE at PRODUCTION is always eligible,
      regardless of policy or age
    - A version older than its policy's retention_seconds is
      ineligible (GC-eligible), unless the policy is disabled
    - disable() turns off automatic expiration for a policy without
      discarding it
    - A version whose artifact has no configured policy is always
      eligible

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, artifact_registry_service, version_resolver, promotion_service):
        """
        Args:
            artifact_registry_service: The registry used to confirm
                an artifact ID is known and active before a policy is
                configured for it. Any object exposing
                `get(artifact_id)`, raising if the artifact is unknown
                or removed, is accepted
            version_resolver: The resolver used to look up a
                version's owning artifact and creation time. Any
                object exposing `resolve(version_id)` (returning an
                object with `.artifact_id` and `.created_at`), raising
                if the version is unknown, is accepted
            promotion_service: The service used to confirm whether a
                version is currently ACTIVE at PRODUCTION. Any object
                exposing `history(artifact_id)` (returning an iterable
                of objects with `.version_id`, `.target_stage`, and
                `.status`) is accepted
        """

        self._artifact_registry_service = artifact_registry_service
        self._version_resolver = version_resolver
        self._promotion_service = promotion_service
        self._policies_by_id = {}
        self._policy_id_by_artifact = {}
        self._lock = RLock()

    def configure(self, artifact_id: str, retention_seconds: float) -> WorkspaceExecutionArtifactRetentionPolicy:
        """
        Configure an artifact's retention policy, replacing any
        policy configured before it with a fresh, enabled one.

        Raises:
            WorkspaceExecutionArtifactRetentionError: If artifact_id
                is None or blank, retention_seconds is not a positive
                number, or the artifact registry does not recognize
                artifact_id as active
        """

        self._validate_id(artifact_id, "artifact ID")

        with self._lock:
            self._ensure_artifact_known(artifact_id)

            policy = WorkspaceExecutionArtifactRetentionPolicy(
                artifact_id=artifact_id,
                retention_seconds=retention_seconds,
            )

            self._policies_by_id[policy.policy_id] = policy
            self._policy_id_by_artifact[artifact_id] = policy.policy_id

            return policy

    def policy(self, artifact_id: str) -> WorkspaceExecutionArtifactRetentionPolicy:
        """
        Look up an artifact's currently configured retention policy.

        Raises:
            WorkspaceExecutionArtifactRetentionError: If artifact_id
                is None or blank, or no policy is configured for it
        """

        self._validate_id(artifact_id, "artifact ID")

        with self._lock:
            return self._resolve_policy(artifact_id)

    def disable(self, policy_id: str) -> WorkspaceExecutionArtifactRetentionPolicy:
        """
        Turn off automatic expiration for a policy, without
        discarding it.

        Raises:
            WorkspaceExecutionArtifactRetentionError: If policy_id is
                None or blank, or no policy is registered under it
        """

        self._validate_id(policy_id, "policy ID")

        with self._lock:
            policy = self._policies_by_id.get(policy_id)

            if policy is None:
                raise WorkspaceExecutionArtifactRetentionError(
                    f"No retention policy is registered under policy ID {policy_id!r}."
                )

            disabled = replace(policy, enabled=False)
            self._policies_by_id[policy_id] = disabled

            return disabled

    def eligible(self, version_id: str) -> bool:
        """
        Whether a version is currently eligible for storage and
        retrieval, i.e. not yet GC-eligible.

        Raises:
            WorkspaceExecutionArtifactRetentionError: If version_id is
                None or blank, or the version resolver does not
                recognize version_id
        """

        self._validate_id(version_id, "version ID")

        with self._lock:
            version = self._resolve_version(version_id)

            if self._is_production_protected(version.artifact_id, version_id):
                return True

            policy_id = self._policy_id_by_artifact.get(version.artifact_id)

            if policy_id is None:
                return True

            policy = self._policies_by_id[policy_id]

            if not policy.enabled:
                return True

            age_seconds = (datetime.now(timezone.utc) - version.created_at).total_seconds()

            return age_seconds <= policy.retention_seconds

    def _is_production_protected(self, artifact_id: str, version_id: str) -> bool:
        try:
            promotions = self._promotion_service.history(artifact_id)
        except Exception:
            return False

        return any(
            promotion.version_id == version_id
            and promotion.target_stage == STAGE_PRODUCTION
            and promotion.status == PROMOTION_STATUS_ACTIVE
            for promotion in promotions
        )

    def _resolve_policy(self, artifact_id: str) -> WorkspaceExecutionArtifactRetentionPolicy:
        policy_id = self._policy_id_by_artifact.get(artifact_id)

        if policy_id is None:
            raise WorkspaceExecutionArtifactRetentionError(
                f"No retention policy is configured for artifact ID {artifact_id!r}."
            )

        return self._policies_by_id[policy_id]

    def _resolve_version(self, version_id: str):
        try:
            return self._version_resolver.resolve(version_id)
        except Exception as error:
            raise WorkspaceExecutionArtifactRetentionError(
                f"No version is known under version ID {version_id!r}."
            ) from error

    def _ensure_artifact_known(self, artifact_id: str) -> None:
        try:
            self._artifact_registry_service.get(artifact_id)
        except Exception as error:
            raise WorkspaceExecutionArtifactRetentionError(
                f"No active artifact is known under artifact ID {artifact_id!r}."
            ) from error

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise WorkspaceExecutionArtifactRetentionError(f"Cannot use an empty or blank {field_name}.")
