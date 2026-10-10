from datetime import (
    datetime,
    timezone,
)

from uuid import uuid4

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_template_deployment_record import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentRecord,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_template_rollback_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRollbackError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_template_rollback_request import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRollbackRequest,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_template_rollback_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRollbackResult,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRollbackService:
    """
    Safely rolls a deployed consumer projection execution capability
    registry event subscription lifecycle policy template back to a
    previously deployed version: verify the target version was
    published, restore it as current, and record the rollback as a
    new deployment without disturbing prior deployment history.

    The service's responsibility is orchestrating rollback, not
    deployment itself, template registration, or version publication.
    It does NOT deploy templates, register templates, publish
    versions, mutate or remove prior deployment records, log, or
    publish events. It operates over a deployment history service
    and a version service supplied at construction time, since both
    carry state that must already reflect prior deployments and
    publications.

    The service is:
    - Deterministic: Same deployment history, version history, and
      request always produce the same outcome
    - Non-destructive: A rollback is recorded as a new deployment;
      no prior deployment record is ever modified or removed
    """

    def __init__(

        self,

        deployment_history_service,

        version_service,

    ):
        """
        Args:
            deployment_history_service: The service recording and
                querying deployment history
            version_service: The service tracking published template
                versions
        """

        self._deployment_history_service = deployment_history_service

        self._version_service = version_service

    def rollback(

        self,

        request,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRollbackResult:
        """
        Roll a deployment back to a previously published version.

        Args:
            request: The rollback request naming the deployment and
                target version

        Returns:
            An immutable rollback result carrying the version that
            was current before the rollback and the version restored

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRollbackError:
                If the request is None, has a blank deployment ID or
                target version, no deployment is found under the
                deployment ID, no version is published under the
                target version, or the target version is already
                current
        """

        self._validate_request(
            request
        )

        deployment_record = self._deployment_history_service.find(
            request.deployment_id
        )

        if deployment_record is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRollbackError(
                    "Cannot roll back: no deployment was found under "
                    f"deployment ID {request.deployment_id!r}."
                )
            )

        template_id = deployment_record.template_id

        current = self._version_service.latest(
            template_id
        )

        if current is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRollbackError(
                    "Cannot roll back: template ID "
                    f"{template_id!r} has no published version history."
                )
            )

        if request.target_version == current.version:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRollbackError(
                    "Cannot roll back: target version "
                    f"{request.target_version!r} is already current."
                )
            )

        if self._version_service.find(

            template_id,

            request.target_version,

        ) is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRollbackError(
                    "Cannot roll back: no version was ever published under "
                    f"target version {request.target_version!r} for "
                    f"template ID {template_id!r}."
                )
            )

        self._version_service.rollback(

            template_id,

            request.target_version,
        )

        rolled_back_at = datetime.now(
            timezone.utc
        )

        self._deployment_history_service.record(

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateDeploymentRecord(
                deployment_id=str(
                    uuid4()
                ),

                template_id=template_id,

                template_version=request.target_version,

                target_registry=deployment_record.target_registry,

                deployed_at=rolled_back_at,
            )
        )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRollbackResult(
                previous_version=current.version,

                restored_version=request.target_version,

                rollback_successful=True,

                rolled_back_at=rolled_back_at,
            )
        )

    def can_rollback(

        self,

        deployment_id,

    ) -> bool:
        """
        Check whether a deployment has an earlier published version
        it could be rolled back to.

        Args:
            deployment_id: The deployment ID to check

        Returns:
            True if the deployment's template has more than one
            published version, False otherwise, including when the
            deployment is not found

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRollbackError:
                If the deployment ID is None or blank
        """

        self._validate_identifier(

            deployment_id,

            "deployment ID",
        )

        deployment_record = self._deployment_history_service.find(
            deployment_id
        )

        if deployment_record is None:

            return False

        history = self._version_service.history(
            deployment_record.template_id
        )

        if history is None:

            return False

        return len(
            history.versions
        ) > 1

    def rollback_history(

        self,

        deployment_id,

    ) -> tuple:
        """
        List every deployment recorded for a deployment's template,
        including any prior rollbacks, in chronological order.

        Args:
            deployment_id: The deployment ID naming the template to
                list deployments for

        Returns:
            An immutable tuple of every deployment record for the
            deployment's template, in chronological order

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRollbackError:
                If the deployment ID is None or blank, or no
                deployment is found under it
        """

        self._validate_identifier(

            deployment_id,

            "deployment ID",
        )

        deployment_record = self._deployment_history_service.find(
            deployment_id
        )

        if deployment_record is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRollbackError(
                    "Cannot list rollback history: no deployment was found "
                    f"under deployment ID {deployment_id!r}."
                )
            )

        return self._deployment_history_service.history(
            deployment_record.template_id
        )

    def _validate_request(

        self,

        request,

    ) -> None:

        if request is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRollbackError(
                    "Cannot roll back from a None request."
                )
            )

        if not isinstance(

            request,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRollbackRequest,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRollbackError(
                    "Cannot roll back: request must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRollbackRequest."
                )
            )

        self._validate_identifier(

            request.deployment_id,

            "deployment ID",
        )

        self._validate_identifier(

            request.target_version,

            "target version",
        )

    def _validate_identifier(

        self,

        identifier,

        label,

    ) -> None:

        if (

            identifier is None

            or not identifier.strip()
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyTemplateRollbackError(
                    f"Cannot roll back with an empty or blank {label}."
                )
            )
