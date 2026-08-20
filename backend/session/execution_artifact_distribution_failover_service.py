from dataclasses import (
    replace,
)

from threading import (
    RLock,
)

from .execution_artifact_distribution_failover import (
    STATUS_FAILED,
    STATUS_SUCCEEDED,
    ExecutionArtifactDistributionFailover,
)

from .execution_artifact_distribution_failover_error import (
    ExecutionArtifactDistributionFailoverError,
)

from .workspace_execution_artifact_distribution import (
    STATUS_PUBLISHED as DISTRIBUTION_STATUS_PUBLISHED,
)


class ExecutionArtifactDistributionFailoverService:
    """
    Automatically switches artifact distribution to a healthy target
    when the primary target fails, using an existing integrity
    service and distribution service as the sources of truth for a
    version's verification status and for actually publishing to a
    target.

    The service's responsibility is failover bookkeeping and
    orchestration only. It does not transmit artifact contents
    itself; it relies on the existing distribution service, given at
    construction time, to publish to a target and report whether that
    publish succeeded.

    Behavior:
    - execute() always verifies integrity first, before attempting any
      target
    - execute() always tries primary_target before any backup
    - execute() tries backup_targets in the exact order registered,
      stopping at the first target that succeeds: selection is
      deterministic, never randomized
    - execute() only reports FAILED once every target, primary and
      every backup, has failed
    - Every execute() call re-evaluates targets from scratch and
      replaces the stored outcome; it never trusts a prior selection

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, integrity_service, distribution_service):
        """
        Args:
            integrity_service: The service used to confirm a version
                currently passes its integrity check before any
                target is attempted. Any object exposing
                `verify(version_id) -> bool` is accepted
            distribution_service: The service used to publish to a
                target and report the outcome. Any object exposing
                `publish(artifact_id, version_id, target)` (returning
                an object with `.status`) is accepted
        """

        self._integrity_service = integrity_service
        self._distribution_service = distribution_service
        self._failovers_by_key = {}
        self._lock = RLock()

    def register(self, artifact_id: str, version_id: str, targets) -> ExecutionArtifactDistributionFailover:
        """
        Register the ordered targets for a version's failover: the
        first target is the primary, every target after it is a
        backup, tried in the order given.

        Raises:
            ExecutionArtifactDistributionFailoverError: If
                artifact_id or version_id is None or blank, or targets
                is empty or contains a blank target
        """

        self._validate_id(artifact_id, "artifact ID")
        self._validate_id(version_id, "version ID")

        target_list = list(targets) if targets is not None else []

        if not target_list:
            raise ExecutionArtifactDistributionFailoverError(
                "Cannot register a failover with no targets: at least a primary target is required."
            )

        primary_target = target_list[0]
        backup_targets = tuple(target_list[1:])

        with self._lock:
            failover = ExecutionArtifactDistributionFailover(
                artifact_id=artifact_id,
                version_id=version_id,
                primary_target=primary_target,
                backup_targets=backup_targets,
            )

            self._failovers_by_key[(artifact_id, version_id)] = failover

            return failover

    def execute(self, artifact_id: str, version_id: str) -> ExecutionArtifactDistributionFailover:
        """
        Verify integrity, then attempt the primary target followed by
        each backup target in order, stopping at the first success.

        Raises:
            ExecutionArtifactDistributionFailoverError: If
                artifact_id or version_id is None or blank, no
                failover is registered for the pair, or the version
                fails its integrity check
        """

        self._validate_id(artifact_id, "artifact ID")
        self._validate_id(version_id, "version ID")

        with self._lock:
            failover = self._resolve(artifact_id, version_id)

            self._ensure_verified(version_id)

            for target in (failover.primary_target, *failover.backup_targets):
                if self._attempt(artifact_id, version_id, target):
                    outcome = replace(failover, status=STATUS_SUCCEEDED, selected_target=target)
                    self._failovers_by_key[(artifact_id, version_id)] = outcome

                    return outcome

            outcome = replace(failover, status=STATUS_FAILED, selected_target=None)
            self._failovers_by_key[(artifact_id, version_id)] = outcome

            return outcome

    def select(self, artifact_id: str, version_id: str):
        """
        The target selected by the most recent execute() call, or
        None if it failed or no execution has run yet.

        Raises:
            ExecutionArtifactDistributionFailoverError: If
                artifact_id or version_id is None or blank, or no
                failover is registered for the pair
        """

        self._validate_id(artifact_id, "artifact ID")
        self._validate_id(version_id, "version ID")

        with self._lock:
            return self._resolve(artifact_id, version_id).selected_target

    def status(self, artifact_id: str, version_id: str) -> ExecutionArtifactDistributionFailover:
        """
        Look up the current failover configuration and outcome for a
        version.

        Raises:
            ExecutionArtifactDistributionFailoverError: If
                artifact_id or version_id is None or blank, or no
                failover is registered for the pair
        """

        self._validate_id(artifact_id, "artifact ID")
        self._validate_id(version_id, "version ID")

        with self._lock:
            return self._resolve(artifact_id, version_id)

    def _attempt(self, artifact_id: str, version_id: str, target: str) -> bool:
        try:
            distribution = self._distribution_service.publish(artifact_id, version_id, target)
        except Exception:
            return False

        return distribution.status == DISTRIBUTION_STATUS_PUBLISHED

    def _ensure_verified(self, version_id: str) -> None:
        try:
            verified = self._integrity_service.verify(version_id)
        except Exception as error:
            raise ExecutionArtifactDistributionFailoverError(
                f"Cannot verify version ID {version_id!r}: it failed its integrity check."
            ) from error

        if not verified:
            raise ExecutionArtifactDistributionFailoverError(
                f"Cannot execute failover for version ID {version_id!r}: it failed its integrity "
                f"check."
            )

    def _resolve(self, artifact_id: str, version_id: str) -> ExecutionArtifactDistributionFailover:
        failover = self._failovers_by_key.get((artifact_id, version_id))

        if failover is None:
            raise ExecutionArtifactDistributionFailoverError(
                f"No failover is registered for artifact ID {artifact_id!r} and version ID "
                f"{version_id!r}."
            )

        return failover

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionArtifactDistributionFailoverError(f"Cannot use an empty or blank {field_name}.")
