from hashlib import sha256

from threading import (
    RLock,
)

from uuid import uuid4

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_policy_rollout_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyRolloutError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_policy_rollout import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyRollout,
    VALID_SESSION_POLICY_ROLLOUT_STRATEGIES,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_policy_rollout_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyRolloutResult,
)

_RUNNING = "RUNNING"
_STOPPED = "STOPPED"


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyRolloutService:
    """
    Gradually rolls out a published version of a consumer projection
    execution capability registry event subscription lifecycle policy
    profile binding workspace execution session policy to newly
    created sessions, according to a configurable adoption strategy,
    instead of switching every session onto it at once.

    The service's responsibility is adoption, not versioning or base
    policy resolution. It relies on the existing session policy
    version service, given at construction time, to establish which
    policy governs a session and, absent an applicable rollout, what
    version it would ordinarily resolve to.

    Behavior:
    - A policy may have at most one running rollout at a time;
      start()-ing a second one for a policy that already has one
      running is rejected
    - resolve() decides a session's outcome only the first time it is
      called for that session_id; every later call for the same
      session_id returns that same, unchanged outcome, so a rollout
      started after a session was already resolved never affects it
    - Under strategy "FULL", every newly resolved session adopts the
      rollout's target version. Under strategy "PERCENTAGE", a
      session adopts it only if it falls within that percentage,
      decided deterministically from its session_id so the same
      session_id always lands on the same side
    - stop() ends a running rollout; a session resolved afterward for
      that policy is unaffected by it

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, policy_version_service, strategy: str, percentage: float):
        """
        Args:
            policy_version_service: The service used to establish
                which policy governs a session and its baseline
                resolved version. Any object exposing
                `resolve(session_id)`, returning an object with
                `policy_id` and `version` attributes, is accepted
            strategy: How every rollout this service starts adopts its
                target version, one of "FULL" or "PERCENTAGE"
            percentage: What percentage of newly created sessions
                adopt a rollout's target version, from 0 to 100.
                Must be 100 when strategy is "FULL"

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyRolloutError:
                If strategy is not one of VALID_SESSION_POLICY_ROLLOUT_STRATEGIES,
                percentage is not a number from 0 to 100, or strategy
                is "FULL" and percentage is not 100
        """

        if strategy not in VALID_SESSION_POLICY_ROLLOUT_STRATEGIES:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyRolloutError(
                f"Invalid strategy {strategy!r}. Must be one of {VALID_SESSION_POLICY_ROLLOUT_STRATEGIES!r}."
            )

        if (
            percentage is None
            or isinstance(percentage, bool)
            or not isinstance(percentage, (int, float))
            or not (0 <= percentage <= 100)
        ):
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyRolloutError(
                f"Invalid percentage {percentage!r}; percentage must be a number from 0 to 100."
            )

        if strategy == "FULL" and percentage != 100:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyRolloutError(
                "Cannot configure a rollout service with strategy 'FULL' and a percentage other than 100."
            )

        self._policy_version_service = policy_version_service
        self._strategy = strategy
        self._percentage = percentage
        self._rollouts_by_id = {}
        self._status_by_rollout_id = {}
        self._active_rollout_id_by_policy_id = {}
        self._results_by_session_id = {}
        self._counts_by_rollout_id = {}
        self._lock = RLock()

    def start(
        self, policy_id: str, version: int
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyRollout:
        """
        Start a rollout of a policy version to newly created sessions.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyRolloutError:
                If policy_id is None or blank, version is not a
                positive integer, or policy_id already has a running
                rollout
        """

        self._validate_id(policy_id, "policy ID")

        if version is None or isinstance(version, bool) or not isinstance(version, int) or version <= 0:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyRolloutError(
                f"Invalid version {version!r}; version must be a positive integer."
            )

        with self._lock:
            if policy_id in self._active_rollout_id_by_policy_id:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyRolloutError(
                    f"Policy ID {policy_id!r} already has a running rollout."
                )

            rollout = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyRollout(
                rollout_id=str(uuid4()),
                policy_id=policy_id,
                target_version=version,
                strategy=self._strategy,
                percentage=self._percentage,
            )

            self._rollouts_by_id[rollout.rollout_id] = rollout
            self._status_by_rollout_id[rollout.rollout_id] = _RUNNING
            self._active_rollout_id_by_policy_id[policy_id] = rollout.rollout_id
            self._counts_by_rollout_id[rollout.rollout_id] = {"total": 0, "applied": 0}

            return rollout

    def stop(self, rollout_id: str) -> None:
        """
        Stop a running rollout.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyRolloutError:
                If rollout_id is None or blank, no rollout is
                registered under it, or it is already stopped
        """

        self._validate_id(rollout_id, "rollout ID")

        with self._lock:
            rollout = self._resolve_rollout(rollout_id)

            if self._status_by_rollout_id[rollout_id] != _RUNNING:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyRolloutError(
                    f"Rollout ID {rollout_id!r} is already stopped."
                )

            self._status_by_rollout_id[rollout_id] = _STOPPED
            self._active_rollout_id_by_policy_id.pop(rollout.policy_id, None)

    def resolve(
        self, session_id: str
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyRolloutResult:
        """
        Decide which version a session adopts, immediately when it is
        created. Returns the same outcome on every later call for the
        same session_id, so a rollout started afterward never affects
        it.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyRolloutError:
                If session_id is None or blank
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            existing = self._results_by_session_id.get(session_id)

            if existing is not None:
                return existing

            base = self._policy_version_service.resolve(session_id)
            rollout_id = self._active_rollout_id_by_policy_id.get(base.policy_id)

            if rollout_id is None:
                result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyRolloutResult(
                    applied=False,
                    assigned_version=base.version,
                )
            else:
                rollout = self._rollouts_by_id[rollout_id]
                applied = self._in_cohort(session_id, rollout)

                result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyRolloutResult(
                    applied=applied,
                    assigned_version=rollout.target_version if applied else base.version,
                )

                counts = self._counts_by_rollout_id[rollout_id]
                counts["total"] += 1

                if applied:
                    counts["applied"] += 1

            self._results_by_session_id[session_id] = result

            return result

    def status(self, rollout_id: str) -> str:
        """
        Report a rollout's current status, "RUNNING" or "STOPPED".

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyRolloutError:
                If rollout_id is None or blank, or no rollout is
                registered under it
        """

        self._validate_id(rollout_id, "rollout ID")

        with self._lock:
            self._resolve_rollout(rollout_id)

            return self._status_by_rollout_id[rollout_id]

    def progress(self, rollout_id: str) -> dict:
        """
        Report how many sessions have been resolved against a
        rollout, and how many of those adopted its target version.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyRolloutError:
                If rollout_id is None or blank, or no rollout is
                registered under it
        """

        self._validate_id(rollout_id, "rollout ID")

        with self._lock:
            self._resolve_rollout(rollout_id)

            return dict(self._counts_by_rollout_id[rollout_id])

    def _in_cohort(
        self,
        session_id: str,
        rollout: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyRollout,
    ) -> bool:
        if rollout.strategy == "FULL":
            return True

        bucket = int(sha256(session_id.encode("utf-8")).hexdigest(), 16) % 100

        return bucket < rollout.percentage

    def _resolve_rollout(
        self, rollout_id: str
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyRollout:
        rollout = self._rollouts_by_id.get(rollout_id)

        if rollout is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyRolloutError(
                f"No rollout is registered under rollout ID {rollout_id!r}."
            )

        return rollout

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyRolloutError(
                f"Cannot operate with an empty or blank {label}."
            )
