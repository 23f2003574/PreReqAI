from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_policy_version_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyVersionError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_policy_version import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyVersion,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_policy_resolution import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyResolution,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyVersionService:
    """
    Publishes immutable, numbered versions of a consumer projection
    execution capability registry event subscription lifecycle policy
    profile binding workspace execution session policy's
    configuration, and binds each session to whichever version was
    latest at the moment it was created, so a policy change published
    later never affects a session already running under an earlier
    one.

    The service's responsibility is versioning and resolution, not
    the base policy or its configuration. It relies on the existing
    session policy service, given at construction time, only to
    resolve which policy governs a session, and on a
    configuration_provider, also given at construction time, to
    capture a policy's current configuration at publish time.

    Behavior:
    - Every publish() call, and every rollback() call, appends a new,
      immutable version; no version is ever mutated or removed, so
      history() always reflects everything ever published
    - rollback() never removes or rewrites the versions between the
      target and the current latest; it appends a new version whose
      configuration copies the target's
    - resolve() binds a session to the latest version at the moment of
      its first call for that session_id, and returns that same
      binding on every subsequent call for it, regardless of what is
      published afterward

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, policy_service, configuration_provider):
        """
        Args:
            policy_service: The service used to resolve which policy
                governs a session. Any object exposing
                `policy(session_id)`, raising if the session has no
                assigned policy, is accepted
            configuration_provider: A callable(policy_id) -> dict
                returning a policy's current configuration, called
                each time publish() runs
        """

        self._policy_service = policy_service
        self._configuration_provider = configuration_provider
        self._versions_by_policy_id = {}
        self._resolutions_by_session_id = {}
        self._lock = RLock()

    def publish(
        self, policy_id: str
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyVersion:
        """
        Publish a new, immutable version of a policy, snapshotting its
        current configuration.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyVersionError:
                If policy_id is None or blank, or configuration_provider
                fails to produce a configuration for it
        """

        self._validate_id(policy_id, "policy ID")

        try:
            configuration = self._configuration_provider(policy_id)
        except Exception as error:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyVersionError(
                f"Could not obtain a configuration for policy ID {policy_id!r}."
            ) from error

        with self._lock:
            versions = self._versions_by_policy_id.setdefault(policy_id, [])

            version = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyVersion(
                policy_id=policy_id,
                version=(versions[-1].version + 1) if versions else 1,
                configuration=configuration,
                created_at=datetime.now(timezone.utc),
            )

            versions.append(version)

            return version

    def resolve(
        self, session_id: str
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyResolution:
        """
        Bind a session to whichever version of its assigned policy is
        latest at the moment of this call, immediately when the
        session is created. Returns the same binding on every later
        call for the same session, regardless of what is published
        afterward.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyVersionError:
                If session_id is None or blank, the session has no
                assigned policy, or that policy has no published
                version
        """

        self._validate_id(session_id, "session ID")

        with self._lock:
            existing = self._resolutions_by_session_id.get(session_id)

            if existing is not None:
                return existing

            try:
                policy = self._policy_service.policy(session_id)
            except Exception as error:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyVersionError(
                    f"Session ID {session_id!r} has no assigned policy."
                ) from error

            latest_version = self.latest(policy.policy_id)

            resolution = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyResolution(
                session_id=session_id,
                policy_id=policy.policy_id,
                version=latest_version.version,
            )

            self._resolutions_by_session_id[session_id] = resolution

            return resolution

    def history(self, policy_id: str) -> tuple:
        """
        List every version ever published for a policy, in the order
        it was published, including versions superseded by a later
        publish or rollback.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyVersionError:
                If policy_id is None or blank
        """

        self._validate_id(policy_id, "policy ID")

        with self._lock:
            return tuple(self._versions_by_policy_id.get(policy_id, []))

    def rollback(
        self, policy_id: str, version: int
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyVersion:
        """
        Publish a new version whose configuration copies an earlier
        version's, making it the new latest version without removing
        or rewriting anything published in between.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyVersionError:
                If policy_id is None or blank, or no version numbered
                version was ever published for policy_id
        """

        self._validate_id(policy_id, "policy ID")

        with self._lock:
            versions = self._versions_by_policy_id.get(policy_id, [])
            target = next((candidate for candidate in versions if candidate.version == version), None)

            if target is None:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyVersionError(
                    f"No version {version!r} was ever published for policy ID {policy_id!r}."
                )

            rolled_back = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyVersion(
                policy_id=policy_id,
                version=versions[-1].version + 1,
                configuration=target.configuration,
                created_at=datetime.now(timezone.utc),
            )

            versions.append(rolled_back)

            return rolled_back

    def latest(
        self, policy_id: str
    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyVersion:
        """
        Look up the most recently published version of a policy.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyVersionError:
                If policy_id is None or blank, or no version was ever
                published for it
        """

        self._validate_id(policy_id, "policy ID")

        with self._lock:
            versions = self._versions_by_policy_id.get(policy_id, [])

            if not versions:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyVersionError(
                    f"No version has ever been published for policy ID {policy_id!r}."
                )

            return versions[-1]

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionPolicyVersionError(
                f"Cannot operate with an empty or blank {label}."
            )
