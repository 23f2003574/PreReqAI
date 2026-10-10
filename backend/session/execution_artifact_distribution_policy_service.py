from threading import (
    RLock,
)

from .execution_artifact_distribution_policy import (
    ExecutionArtifactDistributionPolicy,
)

from .execution_artifact_distribution_policy_assignment import (
    ExecutionArtifactDistributionPolicyAssignment,
)

from .execution_artifact_distribution_policy_error import (
    ExecutionArtifactDistributionPolicyError,
)


class ExecutionArtifactDistributionPolicyService:
    """
    Defines reusable distribution policies and validates artifacts
    against whichever policy is currently assigned to a channel,
    using an existing execution artifact registry, encryption
    service, signing service, and integrity service as the sources of
    truth for an artifact's type and its recorded encryption,
    signature, and integrity state.

    The service's responsibility is policy and assignment bookkeeping
    and validation only. It does not encrypt, sign, or checksum
    artifacts itself.

    Behavior:
    - A channel has at most one active policy at a time; assign()
      replaces whatever was previously assigned
    - remove() only succeeds when the given policy_id is in fact the
      channel's current assignment, guarding against accidentally
      unassigning a different, more recently assigned policy
    - validate() always checks an artifact's type against
      allowed_types, regardless of which of require_encryption,
      require_signature, and require_integrity are enabled: a
      disabled requirement is skipped, but never weakens or bypasses
      the checks that remain enabled
    - validate() raises on the first unmet requirement rather than
      silently returning a boolean, so a caller learns exactly why an
      artifact was rejected

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(
        self,
        execution_artifact_service,
        execution_artifact_encryption_service,
        execution_artifact_signing_service,
        execution_artifact_integrity_service,
    ):
        """
        Args:
            execution_artifact_service: The registry used to confirm
                an artifact ID is known and to look up its type. Any
                object exposing `get(artifact_id)` (returning an
                object with a `.type`), raising if the artifact is
                unknown, is accepted
            execution_artifact_encryption_service: The service used to
                confirm an artifact is currently encrypted when a
                policy requires it. Any object exposing
                `verify(artifact_id)`, raising if it is not, is
                accepted
            execution_artifact_signing_service: The service used to
                confirm an artifact has a recorded signature when a
                policy requires it. Any object exposing
                `status(artifact_id)`, raising if it has none, is
                accepted
            execution_artifact_integrity_service: The service used to
                confirm an artifact has a recorded integrity checksum
                when a policy requires it. Any object exposing
                `status(artifact_id)`, raising if it has none, is
                accepted
        """

        self._execution_artifact_service = execution_artifact_service
        self._execution_artifact_encryption_service = execution_artifact_encryption_service
        self._execution_artifact_signing_service = execution_artifact_signing_service
        self._execution_artifact_integrity_service = execution_artifact_integrity_service
        self._policies_by_id = {}
        self._assignment_by_channel = {}
        self._lock = RLock()

    def register(self, policy: ExecutionArtifactDistributionPolicy) -> ExecutionArtifactDistributionPolicy:
        """
        Register a new distribution policy.

        Raises:
            ExecutionArtifactDistributionPolicyError: If policy is not
                an ExecutionArtifactDistributionPolicy, or its policy
                ID is already registered
        """

        if not isinstance(policy, ExecutionArtifactDistributionPolicy):
            raise ExecutionArtifactDistributionPolicyError(
                "Cannot register an invalid policy: policy must be an ExecutionArtifactDistributionPolicy."
            )

        with self._lock:
            if policy.policy_id in self._policies_by_id:
                raise ExecutionArtifactDistributionPolicyError(
                    f"Policy ID {policy.policy_id!r} is already registered."
                )

            self._policies_by_id[policy.policy_id] = policy

            return policy

    def assign(self, policy_id: str, channel_id: str) -> ExecutionArtifactDistributionPolicyAssignment:
        """
        Assign a registered policy to a channel as its single active
        policy, replacing any previous assignment.

        Raises:
            ExecutionArtifactDistributionPolicyError: If policy_id or
                channel_id is None or blank, or no policy is
                registered under policy_id
        """

        self._validate_id(policy_id, "policy ID")
        self._validate_id(channel_id, "channel ID")

        with self._lock:
            self._resolve_policy(policy_id)

            assignment = ExecutionArtifactDistributionPolicyAssignment(policy_id=policy_id, channel_id=channel_id)
            self._assignment_by_channel[channel_id] = assignment

            return assignment

    def remove(self, policy_id: str, channel_id: str) -> ExecutionArtifactDistributionPolicyAssignment:
        """
        Remove a channel's active policy assignment.

        Raises:
            ExecutionArtifactDistributionPolicyError: If policy_id or
                channel_id is None or blank, or channel_id's current
                assignment is not to policy_id
        """

        self._validate_id(policy_id, "policy ID")
        self._validate_id(channel_id, "channel ID")

        with self._lock:
            assignment = self._assignment_by_channel.get(channel_id)

            if assignment is None or assignment.policy_id != policy_id:
                raise ExecutionArtifactDistributionPolicyError(
                    f"Channel ID {channel_id!r} does not currently have policy ID {policy_id!r} assigned."
                )

            del self._assignment_by_channel[channel_id]

            return assignment

    def policy(self, channel_id: str) -> ExecutionArtifactDistributionPolicy:
        """
        Look up a channel's currently active policy.

        Raises:
            ExecutionArtifactDistributionPolicyError: If channel_id is
                None or blank, or the channel has no active policy
                assigned
        """

        self._validate_id(channel_id, "channel ID")

        with self._lock:
            return self._resolve_policy(self._resolve_assignment(channel_id).policy_id)

    def validate(self, artifact_id: str, channel_id: str) -> bool:
        """
        Validate an artifact against a channel's active policy.

        Raises:
            ExecutionArtifactDistributionPolicyError: If artifact_id
                or channel_id is None or blank, the channel has no
                active policy assigned, the execution artifact
                registry does not recognize artifact_id, the
                artifact's type is not in the policy's allowed_types,
                or a requirement the policy enables is unmet
        """

        self._validate_id(artifact_id, "artifact ID")
        self._validate_id(channel_id, "channel ID")

        with self._lock:
            policy = self._resolve_policy(self._resolve_assignment(channel_id).policy_id)
            artifact = self._get_artifact(artifact_id)

            if artifact.type not in policy.allowed_types:
                raise ExecutionArtifactDistributionPolicyError(
                    f"Artifact ID {artifact_id!r} has type {artifact.type!r}, not permitted by policy "
                    f"{policy.policy_id!r} for channel ID {channel_id!r}."
                )

            if policy.require_encryption:
                self._require(
                    lambda: self._execution_artifact_encryption_service.verify(artifact_id),
                    f"Cannot distribute artifact ID {artifact_id!r} to channel ID {channel_id!r}: policy "
                    f"{policy.policy_id!r} requires encryption, but none is recorded.",
                )

            if policy.require_signature:
                self._require(
                    lambda: self._execution_artifact_signing_service.status(artifact_id),
                    f"Cannot distribute artifact ID {artifact_id!r} to channel ID {channel_id!r}: policy "
                    f"{policy.policy_id!r} requires a signature, but none is recorded.",
                )

            if policy.require_integrity:
                self._require(
                    lambda: self._execution_artifact_integrity_service.status(artifact_id),
                    f"Cannot distribute artifact ID {artifact_id!r} to channel ID {channel_id!r}: policy "
                    f"{policy.policy_id!r} requires an integrity checksum, but none is recorded.",
                )

            return True

    def _require(self, check, message: str) -> None:
        try:
            check()
        except Exception as error:
            raise ExecutionArtifactDistributionPolicyError(message) from error

    def _resolve_assignment(self, channel_id: str) -> ExecutionArtifactDistributionPolicyAssignment:
        assignment = self._assignment_by_channel.get(channel_id)

        if assignment is None:
            raise ExecutionArtifactDistributionPolicyError(f"Channel ID {channel_id!r} has no active policy.")

        return assignment

    def _resolve_policy(self, policy_id: str) -> ExecutionArtifactDistributionPolicy:
        policy = self._policies_by_id.get(policy_id)

        if policy is None:
            raise ExecutionArtifactDistributionPolicyError(f"No policy is registered under policy ID {policy_id!r}.")

        return policy

    def _get_artifact(self, artifact_id: str):
        try:
            return self._execution_artifact_service.get(artifact_id)
        except Exception as error:
            raise ExecutionArtifactDistributionPolicyError(
                f"No artifact is known under artifact ID {artifact_id!r}."
            ) from error

    @staticmethod
    def _validate_id(value: str, field_name: str) -> None:
        if value is None or not value.strip():
            raise ExecutionArtifactDistributionPolicyError(f"Cannot use an empty or blank {field_name}.")
