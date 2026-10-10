from datetime import (
    datetime,
    timezone,
)

from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_cleanup_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCleanupError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_cleanup_policy import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCleanupPolicy,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_session_cleanup_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCleanupResult,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_binding_workspace_execution_session_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionStatus,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCleanupService:
    """
    Automatically retires consumer projection execution capability
    registry event subscription lifecycle policy profile binding
    workspace execution sessions that have gone stale under one or
    more configurable cleanup policies, so runtime storage stays
    healthy without manual intervention.

    The service's responsibility is deciding and reporting what is
    stale, not owning session storage. It does NOT delete a session
    from wherever it is actually persisted; the execution session
    service, given at construction time, does not itself expose a way
    to enumerate or delete sessions, and this service does not
    refactor it to add one. Instead, this service is handed a
    sessions_provider — a zero-argument callable returning every
    session currently known — and reports which of those sessions
    each policy would retire; "deleted" means retired from this
    service's own further consideration, not removed from wherever
    sessions_provider's caller actually stores them.

    Behavior:
    - A session still active is never eligible for retirement, under
      any policy
    - archive_before_delete=True copies an eligible session into this
      service's own archive before it is retired
    - preview() computes the same tally as run() without retiring, or
      archiving, anything
    - Every scan updates cumulative counters returned by statistics()

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    """

    def __init__(self, sessions_provider, policies=()):
        """
        Args:
            sessions_provider: A zero-argument callable returning an
                iterable of every session currently known, each
                exposing `session_id`, `status`, `started_at`, and
                `finished_at` attributes
            policies: The ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCleanupPolicy
                instances to register upfront, keyed by their
                policy_id

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCleanupError:
                If two given policies share a policy_id
        """

        self._sessions_provider = sessions_provider
        self._policies_by_id = {}
        self._archive = {}
        self._retired_session_ids = set()
        self._cumulative_scanned = 0
        self._cumulative_archived = 0
        self._cumulative_deleted = 0
        self._lock = RLock()

        for policy in policies:
            if policy.policy_id in self._policies_by_id:
                raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCleanupError(
                    f"Policy ID {policy.policy_id!r} is already registered."
                )

            self._policies_by_id[policy.policy_id] = policy

    def run(self) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCleanupResult:
        """
        Scan every known session against every registered policy,
        archiving and retiring whichever are eligible.
        """

        with self._lock:
            return self._scan(list(self._policies_by_id.values()), mutate=True)

    def preview(self) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCleanupResult:
        """
        Compute what run() would do against every registered policy,
        without archiving or retiring anything.
        """

        with self._lock:
            return self._scan(list(self._policies_by_id.values()), mutate=False)

    def apply(self, policy_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCleanupResult:
        """
        Scan every known session against a single registered policy,
        archiving and retiring whichever are eligible.

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCleanupError:
                If policy_id is None or blank, or no policy is
                registered under it
        """

        self._validate_id(policy_id, "policy ID")

        with self._lock:
            policy = self._resolve_policy(policy_id)

            return self._scan([policy], mutate=True)

    def expired(self) -> tuple:
        """
        List every currently known session that is eligible for
        retirement under at least one registered policy, without
        archiving or retiring anything.
        """

        with self._lock:
            now = datetime.now(timezone.utc)
            policies = list(self._policies_by_id.values())

            return tuple(
                session
                for session in self._sessions_provider()
                if session.session_id not in self._retired_session_ids
                and any(self._is_eligible(policy, session, now) for policy in policies)
            )

    def statistics(self) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCleanupResult:
        """
        Report cumulative scanned, archived, and deleted counts across
        every run() and apply() call made so far. preview() never
        contributes to these counts.
        """

        with self._lock:
            return ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCleanupResult(
                scanned=self._cumulative_scanned,
                archived=self._cumulative_archived,
                deleted=self._cumulative_deleted,
            )

    def _scan(self, policies: list, mutate: bool) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCleanupResult:
        now = datetime.now(timezone.utc)

        sessions = tuple(self._sessions_provider())
        scanned = len(sessions)
        archived = 0
        deleted = 0

        for session in sessions:
            if session.session_id in self._retired_session_ids:
                continue

            matching_policy = next(
                (policy for policy in policies if self._is_eligible(policy, session, now)),
                None,
            )

            if matching_policy is None:
                continue

            if matching_policy.archive_before_delete:
                archived += 1

                if mutate:
                    self._archive[session.session_id] = session

            deleted += 1

            if mutate:
                self._retired_session_ids.add(session.session_id)

        result = ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCleanupResult(
            scanned=scanned,
            archived=archived,
            deleted=deleted,
        )

        if mutate:
            self._cumulative_scanned += scanned
            self._cumulative_archived += archived
            self._cumulative_deleted += deleted

        return result

    def _is_eligible(
        self,
        policy: ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCleanupPolicy,
        session,
        now: datetime,
    ) -> bool:
        if session.status == ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionStatus.ACTIVE:
            return False

        if policy.completed_only and session.status != ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceExecutionSessionStatus.FINISHED:
            return False

        reference_time = session.finished_at if session.finished_at is not None else session.started_at
        age_seconds = (now - reference_time).total_seconds()

        return age_seconds >= policy.max_age

    def _resolve_policy(self, policy_id: str) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCleanupPolicy:
        policy = self._policies_by_id.get(policy_id)

        if policy is None:
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCleanupError(
                f"No session cleanup policy is registered under policy ID {policy_id!r}."
            )

        return policy

    def _validate_id(self, identifier: str, label: str) -> None:
        if identifier is None or not identifier.strip():
            raise ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileBindingWorkspaceSessionCleanupError(
                f"Cannot operate with an empty or blank {label}."
            )
