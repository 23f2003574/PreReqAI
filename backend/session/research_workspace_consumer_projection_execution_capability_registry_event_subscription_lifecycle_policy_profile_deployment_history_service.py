from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_deployment_history import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentHistory,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_deployment_history_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentHistoryError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_deployment_record import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentRecord,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_deployment_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentStatus,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentHistoryService:
    """
    Records and queries the deployment history of consumer
    projection execution capability registry event subscription
    lifecycle policy profiles, for auditing, querying, and tracing
    across environments.

    The service's responsibility is recording and read-only
    querying, not deployment itself, profile registration, or
    resolution. It does NOT deploy profiles, register profiles,
    resolve profiles, mutate a recorded record, persist history
    externally, log, or publish events.

    The service is:
    - Thread-safe: All mutation and reads are guarded by an internal
      lock
    - Duplicate-free: No two records may share a deployment ID
    - Chronological: Records are listed in the order they were
      recorded
    - Append-only: Records are never replaced or removed once
      recorded
    """

    def __init__(self):

        self._history = (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentHistory(
                records=()
            )
        )

        self._lock = RLock()

    def record(

        self,

        deployment_record,

    ) -> None:
        """
        Record a deployment.

        Args:
            deployment_record: The deployment record to append to
                the history

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentHistoryError:
                If the record is None, not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentRecord,
                has a blank deployment ID, profile ID, or target
                environment, has an unknown deployment status, or its
                deployment ID has already been recorded
        """

        self._validate_record(
            deployment_record
        )

        with self._lock:

            if any(

                existing.deployment_id == deployment_record.deployment_id

                for existing

                in self._history.records
            ):

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentHistoryError(
                        "Cannot record a deployment: deployment ID "
                        f"{deployment_record.deployment_id!r} has already "
                        "been recorded."
                    )
                )

            self._history = (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentHistory(
                    records=self._history.records + (deployment_record,)
                )
            )

    def find(

        self,

        deployment_id,

    ):
        """
        Find the record for a deployment ID.

        Args:
            deployment_id: The deployment ID to look up

        Returns:
            The matching deployment record, or None if no deployment
            with that ID has been recorded
        """

        with self._lock:

            for existing in self._history.records:

                if existing.deployment_id == deployment_id:

                    return existing

            return None

    def list(

        self,

    ) -> tuple:
        """
        List every recorded deployment.

        Returns:
            An immutable tuple of every deployment record, in
            chronological order
        """

        with self._lock:

            return self._history.records

    def history(

        self,

        profile_id,

    ) -> tuple:
        """
        List every recorded deployment for a profile.

        Args:
            profile_id: The profile ID to filter by

        Returns:
            An immutable tuple of every deployment record for the
            profile, in chronological order
        """

        with self._lock:

            return tuple(

                record

                for record

                in self._history.records

                if record.profile_id == profile_id
            )

    def history_for_environment(

        self,

        target_environment,

    ) -> tuple:
        """
        List every recorded deployment for a target environment.

        Args:
            target_environment: The target environment to filter by

        Returns:
            An immutable tuple of every deployment record published
            into the environment, in chronological order
        """

        with self._lock:

            return tuple(

                record

                for record

                in self._history.records

                if record.target_environment == target_environment
            )

    def _validate_record(

        self,

        record,

    ) -> None:

        if record is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentHistoryError(
                    "Cannot record a None deployment record."
                )
            )

        if not isinstance(

            record,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentRecord,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentHistoryError(
                    "Cannot record a deployment: record must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentRecord."
                )
            )

        if (

            record.deployment_id is None

            or not record.deployment_id.strip()
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentHistoryError(
                    "Cannot record a deployment with an empty or blank "
                    "deployment ID."
                )
            )

        if (

            record.profile_id is None

            or not record.profile_id.strip()
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentHistoryError(
                    "Cannot record a deployment with an empty or blank "
                    "profile ID."
                )
            )

        if (

            record.target_environment is None

            or not record.target_environment.strip()
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentHistoryError(
                    "Cannot record a deployment with an empty or blank "
                    "target environment."
                )
            )

        if not isinstance(

            record.deployment_status,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentStatus,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentHistoryError(
                    "Cannot record a deployment with an unknown deployment "
                    f"status {record.deployment_status!r}."
                )
            )
