from threading import (
    RLock,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_template_deployment_history import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentHistory,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_template_deployment_history_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentHistoryError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_template_deployment_record import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentRecord,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentHistoryService:
    """
    Records and queries the deployment history of consumer
    projection execution capability registry event subscription
    lifecycle policy templates, for auditing, rollback decisions,
    and deployment reporting.

    The service's responsibility is recording and read-only
    querying, not deployment itself, template registration, or
    resolution. It does NOT deploy templates, register templates,
    resolve templates, mutate a recorded record, persist history
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
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentHistory(
                records=()
            )
        )

        self._lock = RLock()

    def record(

        self,

        record,

    ) -> None:
        """
        Record a deployment.

        Args:
            record: The deployment record to append to the history

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentHistoryError:
                If the record is None, not a
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentRecord,
                has a blank deployment ID or template ID, or its
                deployment ID has already been recorded
        """

        self._validate_record(
            record
        )

        with self._lock:

            if any(

                existing.deployment_id == record.deployment_id

                for existing

                in self._history.records
            ):

                raise (
                    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentHistoryError(
                        "Cannot record a deployment: deployment ID "
                        f"{record.deployment_id!r} has already been "
                        "recorded."
                    )
                )

            self._history = (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentHistory(
                    records=self._history.records + (record,)
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

        template_id,

    ) -> tuple:
        """
        List every recorded deployment for a template.

        Args:
            template_id: The template ID to filter by

        Returns:
            An immutable tuple of every deployment record for the
            template, in chronological order
        """

        with self._lock:

            return tuple(

                record

                for record

                in self._history.records

                if record.template_id == template_id
            )

    def history_for_registry(

        self,

        registry_id,

    ) -> tuple:
        """
        List every recorded deployment for a target registry.

        Args:
            registry_id: The target registry identifier to filter by

        Returns:
            An immutable tuple of every deployment record published
            into the registry, in chronological order
        """

        with self._lock:

            return tuple(

                record

                for record

                in self._history.records

                if record.target_registry == registry_id
            )

    def _validate_record(

        self,

        record,

    ) -> None:

        if record is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentHistoryError(
                    "Cannot record a None deployment record."
                )
            )

        if not isinstance(

            record,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentRecord,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentHistoryError(
                    "Cannot record a deployment: record must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentRecord."
                )
            )

        if (

            record.deployment_id is None

            or not record.deployment_id.strip()
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentHistoryError(
                    "Cannot record a deployment with an empty or blank "
                    "deployment ID."
                )
            )

        if (

            record.template_id is None

            or not record.template_id.strip()
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentHistoryError(
                    "Cannot record a deployment with an empty or blank "
                    "template ID."
                )
            )
