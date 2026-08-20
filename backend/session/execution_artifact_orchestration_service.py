from threading import (
    RLock,
)

from .execution_artifact_decision import (
    ACTION_DISTRIBUTE,
    ACTION_PROMOTE,
    ACTION_PUBLISH,
    ACTION_RELEASE,
    ACTION_RETIRE,
    ExecutionArtifactDecision,
)

from .execution_artifact_decision_error import (
    ExecutionArtifactDecisionError,
)

from .execution_artifact_distribution_failover import (
    STATUS_SUCCEEDED as FAILOVER_STATUS_SUCCEEDED,
)


class ExecutionArtifactOrchestrationService:
    """
    Unifies artifact registration, versioning, integrity, promotion,
    retention, distribution, failover, and release channels into one
    lifecycle pipeline, by reusing the existing services for each of
    those concerns rather than re-implementing their rules.

    The service's responsibility is decision recording and sequencing
    only. It never re-implements a rule already enforced by the
    service it delegates to; it only decides whether to delegate, and
    records the outcome as a single deterministic decision.

    Behavior:
    - publish() never proceeds without a passing integrity check
    - promote() delegates to the promotion service, which itself
      enforces integrity, forward-only movement, and production
      immutability
    - distribute() always goes through the failover service, so a
      failed primary target is retried against backups before the
      action is considered blocked
    - release() requires the version to have at least one currently
      published distribution target before delegating to the release
      channel service, which itself re-verifies integrity
    - retire() never proceeds while the garbage collection service
      still considers the version protected
    - Every action records exactly one ExecutionArtifactDecision;
      repeating the same action against unchanged state always
      records the same allowed/reason outcome
    - No action raises for a blocked business rule: the decision's
      allowed and reason fields carry that outcome instead

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(
        self,
        integrity_service,
        promotion_service,
        distribution_service,
        failover_service,
        release_channel_service,
        garbage_collection_service,
        version_resolver,
    ):
        """
        Args:
            integrity_service: Used by publish() to confirm a version
                currently passes its integrity check. Any object
                exposing `verify(version_id) -> bool` is accepted
            promotion_service: Used by promote() to move a version
                forward through stages. Any object exposing
                `promote(artifact_id, version_id, stage)` is accepted
            distribution_service: Used by release() to confirm a
                version currently has at least one published
                distribution target. Any object exposing
                `targets(version_id)` is accepted
            failover_service: Used by distribute() to publish a
                version through its registered primary and backup
                targets. Any object exposing
                `execute(artifact_id, version_id)` (returning an
                object with `.status` and `.selected_target`) is
                accepted
            release_channel_service: Used by release() to make a
                version the current version of a channel. Any object
                exposing `release(artifact_id, version_id, channel)`
                is accepted
            garbage_collection_service: Used by retire() to confirm a
                version is unprotected before staging it for
                collection. Any object exposing `protected(version_id)
                -> bool` and `mark(version_id)` is accepted
            version_resolver: Used by retire() to look up a bare
                version_id's owning artifact. Any object exposing
                `resolve(version_id)` (returning an object with
                `.artifact_id`), raising if the version is unknown, is
                accepted
        """

        self._integrity_service = integrity_service
        self._promotion_service = promotion_service
        self._distribution_service = distribution_service
        self._failover_service = failover_service
        self._release_channel_service = release_channel_service
        self._garbage_collection_service = garbage_collection_service
        self._version_resolver = version_resolver
        self._decisions_by_key = {}
        self._lock = RLock()

    def publish(self, artifact_id: str, version_id: str) -> ExecutionArtifactDecision:
        """
        Allow publication only once a version passes its integrity
        check.
        """

        self._validate_id(artifact_id, "artifact ID")
        self._validate_id(version_id, "version ID")

        with self._lock:
            if self._verify(version_id):
                return self._record(artifact_id, version_id, ACTION_PUBLISH, True, "version passed integrity check")

            return self._record(
                artifact_id, version_id, ACTION_PUBLISH, False, "version failed integrity check"
            )

    def promote(self, artifact_id: str, version_id: str, stage: str) -> ExecutionArtifactDecision:
        """
        Promote a version forward through stages, deferring every
        promotion rule to the promotion service.
        """

        self._validate_id(artifact_id, "artifact ID")
        self._validate_id(version_id, "version ID")

        with self._lock:
            try:
                self._promotion_service.promote(artifact_id, version_id, stage)
            except Exception as error:
                return self._record(artifact_id, version_id, ACTION_PROMOTE, False, str(error))

            return self._record(artifact_id, version_id, ACTION_PROMOTE, True, f"promoted to {stage}")

    def distribute(self, artifact_id: str, version_id: str) -> ExecutionArtifactDecision:
        """
        Publish a version through its registered failover targets,
        preferring the primary and falling back to a healthy backup.
        """

        self._validate_id(artifact_id, "artifact ID")
        self._validate_id(version_id, "version ID")

        with self._lock:
            try:
                outcome = self._failover_service.execute(artifact_id, version_id)
            except Exception as error:
                return self._record(artifact_id, version_id, ACTION_DISTRIBUTE, False, str(error))

            if outcome.status == FAILOVER_STATUS_SUCCEEDED:
                return self._record(
                    artifact_id,
                    version_id,
                    ACTION_DISTRIBUTE,
                    True,
                    f"distributed to {outcome.selected_target}",
                )

            return self._record(
                artifact_id, version_id, ACTION_DISTRIBUTE, False, "every distribution target failed"
            )

    def release(self, artifact_id: str, version_id: str, channel: str) -> ExecutionArtifactDecision:
        """
        Release a version to a channel only once it has at least one
        currently published distribution target, deferring integrity
        and channel rules to the release channel service.
        """

        self._validate_id(artifact_id, "artifact ID")
        self._validate_id(version_id, "version ID")

        with self._lock:
            if not self._distribution_service.targets(version_id):
                return self._record(
                    artifact_id,
                    version_id,
                    ACTION_RELEASE,
                    False,
                    "version has no currently published distribution target",
                )

            try:
                self._release_channel_service.release(artifact_id, version_id, channel)
            except Exception as error:
                return self._record(artifact_id, version_id, ACTION_RELEASE, False, str(error))

            return self._record(artifact_id, version_id, ACTION_RELEASE, True, f"released to {channel}")

    def retire(self, version_id: str) -> ExecutionArtifactDecision:
        """
        Stage a version for garbage collection only once it is no
        longer protected by retention or production status.
        """

        self._validate_id(version_id, "version ID")

        with self._lock:
            artifact_id = self._resolve_artifact_id(version_id)

            if self._garbage_collection_service.protected(version_id):
                return self._record(
                    artifact_id, version_id, ACTION_RETIRE, False, "version is protected and cannot be retired"
                )

            try:
                self._garbage_collection_service.mark(version_id)
            except Exception as error:
                return self._record(artifact_id, version_id, ACTION_RETIRE, False, str(error))

            return self._record(
                artifact_id, version_id, ACTION_RETIRE, True, "version marked for garbage collection"
            )

    def decision(self, artifact_id: str, version_id: str) -> ExecutionArtifactDecision:
        """
        Look up the most recently recorded decision for an artifact
        version.

        Raises:
            ExecutionArtifactDecisionError: If artifact_id or
                version_id is None or blank, or no decision has been
                recorded for the pair
        """

        self._validate_id(artifact_id, "artifact ID")
        self._validate_id(version_id, "version ID")

        with self._lock:
            decision = self._decisions_by_key.get((artifact_id, version_id))

            if decision is None:
                raise ExecutionArtifactDecisionError(
                    f"No decision has been recorded for artifact ID {artifact_id!r} and version "
                    f"ID {version_id!r}."
                )

            return decision

    def _record(
        self, artifact_id: str, version_id: str, action: str, allowed: bool, reason: str
    ) -> ExecutionArtifactDecision:
        decision = ExecutionArtifactDecision(
            artifact_id=artifact_id,
            version_id=version_id,
            action=action,
            allowed=allowed,
            reason=reason,
        )

        self._decisions_by_key[(artifact_id, version_id)] = decision

        return decision

    def _verify(self, version_id: str) -> bool:
        try:
            return bool(self._integrity_service.verify(version_id))
        except Exception:
            return False

    def _resolve_artifact_id(self, version_id: str) -> str:
        try:
            return self._version_resolver.resolve(version_id).artifact_id
        except Exception as error:
            raise ExecutionArtifactDecisionError(
                f"No version is known under version ID {version_id!r}."
            ) from error

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionArtifactDecisionError(f"Cannot use an empty or blank {field_name}.")
