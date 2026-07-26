from datetime import (
    datetime,
    timezone,
)

from uuid import uuid4

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_compatibility_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_deployment_record import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentRecord,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_deployment_status import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentStatus,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_rollback_error import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRollbackError,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_rollback_request import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRollbackRequest,
)

from .research_workspace_consumer_projection_execution_capability_registry_event_subscription_lifecycle_policy_profile_rollback_result import (
    ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRollbackResult,
)


class ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRollbackService:
    """
    Safely rolls a deployed consumer projection execution capability
    registry event subscription lifecycle policy profile back to a
    previously deployed version within a target environment: verify
    the target version was actually deployed there before, verify
    its compatibility, and record the rollback as a new deployment
    without disturbing prior deployment history.

    The service's responsibility is orchestrating rollback, not
    deployment itself, profile registration, or version publication.
    It does NOT deploy profiles, register profiles, publish
    versions, mutate or remove prior deployment records, log, or
    publish events. It operates over a deployment history service and
    a compatibility service supplied at construction time, since both
    carry state or logic that must already reflect prior deployments
    and compatibility rules.

    The service is:
    - Deterministic: Same deployment history, compatibility rules,
      and request always produce the same outcome, including the
      rollback identifier itself
    - Non-destructive: A rollback is recorded as a new deployment; no
      prior deployment record is ever modified or removed
    """

    def __init__(

        self,

        deployment_history_service,

        compatibility_service,

    ):
        """
        Args:
            deployment_history_service: The service recording and
                querying deployment history
            compatibility_service: The service used to verify a
                target version's compatibility before restoration
        """

        self._deployment_history_service = deployment_history_service

        self._compatibility_service = compatibility_service

    def rollback(

        self,

        request,

    ) -> ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRollbackResult:
        """
        Roll a profile's deployment in a target environment back to a
        previously deployed version.

        Args:
            request: The rollback request naming the profile, target
                environment, target version, and reason

        Returns:
            An immutable rollback result carrying the version that
            was active before the rollback and the version restored

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRollbackError:
                If the request is None, has a blank profile ID,
                target environment, or target version, no deployment
                history exists for the profile and target
                environment, the target version is already active, no
                deployment history entry names the target version, or
                the target version fails compatibility verification
        """

        self._validate_request(
            request
        )

        environment_history = self._environment_history(

            request.profile_id,

            request.target_environment,
        )

        if not environment_history:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRollbackError(
                    "Cannot roll back: no deployment history exists for "
                    f"profile ID {request.profile_id!r} in target "
                    f"environment {request.target_environment!r}."
                )
            )

        current_record = environment_history[-1]

        if request.target_version == current_record.version:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRollbackError(
                    "Cannot roll back: target version "
                    f"{request.target_version!r} is already active in "
                    f"target environment {request.target_environment!r}."
                )
            )

        if not any(

            record.version == request.target_version

            for record

            in environment_history
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRollbackError(
                    "Cannot roll back: target version "
                    f"{request.target_version!r} was never deployed to "
                    f"target environment {request.target_environment!r} "
                    f"for profile ID {request.profile_id!r}."
                )
            )

        try:

            compatibility_result = self._compatibility_service.check_version(

                request.profile_id,

                request.target_version,
            )

        except ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityError as error:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRollbackError(
                    "Cannot roll back: compatibility could not be verified "
                    f"for target version {request.target_version!r}."
                )
            ) from error

        if not compatibility_result.compatible:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRollbackError(
                    "Cannot roll back: target version "
                    f"{request.target_version!r} failed compatibility "
                    "verification."
                )
            )

        rolled_back_at = datetime.now(
            timezone.utc
        )

        self._deployment_history_service.record(
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentRecord(
                deployment_id=str(
                    uuid4()
                ),

                profile_id=request.profile_id,

                version=request.target_version,

                target_environment=request.target_environment,

                deployed_at=rolled_back_at,

                deployment_status=ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileDeploymentStatus.SUCCEEDED,
            )
        )

        return (
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRollbackResult(
                previous_version=current_record.version,

                restored_version=request.target_version,

                rollback_id=self._generate_rollback_id(

                    request.profile_id,

                    request.target_environment,

                    request.target_version,
                ),

                rolled_back_at=rolled_back_at,

                successful=True,
            )
        )

    def can_rollback(

        self,

        profile_id,

        target_environment,

        target_version,

    ) -> bool:
        """
        Check whether a profile's deployment in a target environment
        can currently be rolled back to a target version.

        Args:
            profile_id: The profile to check
            target_environment: The target environment to check
            target_version: The version to check

        Returns:
            True if the target version was previously deployed to
            the target environment, is not already active, and
            passes compatibility verification, False otherwise

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRollbackError:
                If the profile ID, target environment, or target
                version is None or blank
        """

        self._validate_identifier(
            profile_id,

            "profile ID",
        )

        self._validate_identifier(
            target_environment,

            "target environment",
        )

        self._validate_identifier(
            target_version,

            "target version",
        )

        environment_history = self._environment_history(

            profile_id,

            target_environment,
        )

        if not environment_history:

            return False

        if environment_history[-1].version == target_version:

            return False

        if not any(

            record.version == target_version

            for record

            in environment_history
        ):

            return False

        try:

            return self._compatibility_service.check_version(

                profile_id,

                target_version,

            ).compatible

        except ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileCompatibilityError:

            return False

    def rollback_history(

        self,

        profile_id,

    ) -> tuple:
        """
        List every deployment recorded for a profile, including any
        prior rollbacks, in chronological order.

        Args:
            profile_id: The profile ID to list deployments for

        Returns:
            An immutable tuple of every deployment record for the
            profile, in chronological order

        Raises:
            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRollbackError:
                If the profile ID is None or blank
        """

        self._validate_identifier(
            profile_id,

            "profile ID",
        )

        return self._deployment_history_service.history(
            profile_id
        )

    def _environment_history(

        self,

        profile_id,

        target_environment,

    ) -> tuple:

        return tuple(

            record

            for record

            in self._deployment_history_service.history(
                profile_id
            )

            if record.target_environment == target_environment
        )

    def _generate_rollback_id(

        self,

        profile_id,

        target_environment,

        target_version,

    ) -> str:

        return f"rollback::{profile_id}::{target_environment}::{target_version}"

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
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRollbackError(
                    f"Cannot roll back with an empty or blank {label}."
                )
            )

    def _validate_request(

        self,

        request,

    ) -> None:

        if request is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRollbackError(
                    "Cannot roll back from a None request."
                )
            )

        if not isinstance(

            request,

            ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRollbackRequest,
        ):

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRollbackError(
                    "Cannot roll back: request must be a "
                    "ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRollbackRequest."
                )
            )

        self._validate_identifier(
            request.profile_id,

            "profile ID",
        )

        self._validate_identifier(
            request.target_environment,

            "target environment",
        )

        self._validate_identifier(
            request.target_version,

            "target version",
        )

        if request.reason is None:

            raise (
                ResearchWorkspaceConsumerProjectionExecutionCapabilityRegistryEventSubscriptionLifecyclePolicyProfileRollbackError(
                    "Cannot roll back with a None reason."
                )
            )
